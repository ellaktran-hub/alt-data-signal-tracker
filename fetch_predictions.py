"""
fetch_predictions.py
Records daily composite-signal predictions for all 50 tickers and fills
in actual price returns as they become available.

Columns in predictions.csv:
  date          — date the prediction was made
  ticker
  signal        — BULLISH / BEARISH / NEUTRAL
  score         — raw vote total (-4 to +4)
  price         — closing price on prediction date
  bullish_pct   — StockTwits bullish % (if available)
  news_sent     — VADER avg sentiment (if available)
  trends_score  — Google Trends score (if available)
  actual_1d     — % price change 1 trading day later (filled in next run)
  actual_3d     — % price change 3 trading days later
  actual_7d     — % price change 7 trading days later
  hit_1d        — True/False: BULLISH→actual>0, BEARISH→actual<0 (NaN for NEUTRAL)
  hit_3d
  hit_7d
"""

from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd

import config

DATA_DIR  = Path(__file__).parent / "data"
PRED_FILE = DATA_DIR / "predictions.csv"

HORIZONS = [(1, "actual_1d", "hit_1d"),
            (3, "actual_3d", "hit_3d"),
            (7, "actual_7d", "hit_7d")]


# ── loaders ───────────────────────────────────────────────────────────────────
def _price_series(ticker):
    p = DATA_DIR / f"prices_{ticker}.csv"
    if not p.exists():
        return pd.Series(dtype=float)
    df = pd.read_csv(p, parse_dates=["date"], index_col="date")
    return df["close_price"].dropna().sort_index()


def _trends_latest(ticker):
    p = DATA_DIR / f"trends_{ticker}.csv"
    if not p.exists():
        return None, None
    df = pd.read_csv(p, parse_dates=["date"], index_col="date")
    if df.empty:
        return None, None
    best = df.mean().idxmax()
    s    = df[best].dropna().sort_index()
    if len(s) < 2:
        return None, None
    return float(s.iloc[-1]), float(s.rolling(7, min_periods=1).mean().iloc[-1])


def _stocktwits_latest(ticker):
    p = DATA_DIR / f"stocktwits_{ticker}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"], index_col="date")
    valid = df.dropna(subset=["message_count"])
    valid = valid[valid["message_count"] > 0]
    if valid.empty:
        return None
    last = valid.iloc[-1]
    return float(last["bullish_count"] / last["message_count"] * 100)


def _news_latest(ticker):
    p = DATA_DIR / f"news_{ticker}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"], index_col="date")
    if "avg_sentiment" not in df.columns:
        return None
    vs = df["avg_sentiment"].dropna()
    return float(vs.iloc[-1]) if len(vs) > 0 else None


# ── signal computation ────────────────────────────────────────────────────────
def _compute_row(ticker, today_str):
    price_s = _price_series(ticker)
    if len(price_s) < 2:
        return None

    latest_price = float(price_s.iloc[-1])
    pct_chg      = (price_s.iloc[-1] - price_s.iloc[-2]) / price_s.iloc[-2] * 100

    votes = []

    # Price vote
    votes.append(1 if pct_chg > 0.5 else (-1 if pct_chg < -0.5 else 0))

    # Google Trends vote
    tr_latest, tr_avg = _trends_latest(ticker)
    trends_score = tr_latest
    if tr_latest is not None and tr_avg is not None:
        votes.append(1 if tr_latest > tr_avg * 1.1 else (-1 if tr_latest < tr_avg * 0.9 else 0))

    # StockTwits vote
    bull_pct = _stocktwits_latest(ticker)
    if bull_pct is not None:
        votes.append(1 if bull_pct > 55 else (-1 if bull_pct < 40 else 0))

    # News vote
    news = _news_latest(ticker)
    if news is not None:
        votes.append(1 if news > 0.1 else (-1 if news < -0.1 else 0))

    score  = sum(votes)
    signal = "BULLISH" if score >= 2 else ("BEARISH" if score <= -2 else "NEUTRAL")

    return {
        "date":         today_str,
        "ticker":       ticker,
        "signal":       signal,
        "score":        score,
        "price":        round(latest_price, 4),
        "bullish_pct":  round(bull_pct, 1)    if bull_pct      is not None else None,
        "news_sent":    round(news, 4)         if news          is not None else None,
        "trends_score": round(trends_score, 1) if trends_score  is not None else None,
        "actual_1d":    None,
        "actual_3d":    None,
        "actual_7d":    None,
        "hit_1d":       None,
        "hit_3d":       None,
        "hit_7d":       None,
    }


# ── fill actuals ──────────────────────────────────────────────────────────────
def _fill_actuals(df):
    price_cache = {}
    for idx, row in df.iterrows():
        ticker     = row["ticker"]
        pred_price = row.get("price")
        if pd.isna(pred_price) or pred_price <= 0:
            continue
        pred_date  = pd.Timestamp(row["date"])

        if ticker not in price_cache:
            price_cache[ticker] = _price_series(ticker)
        price_s = price_cache[ticker]
        if price_s.empty:
            continue

        future = price_s[price_s.index > pred_date]
        sig    = row["signal"]

        for days, col_ret, col_hit in HORIZONS:
            if pd.notna(row.get(col_ret)):
                continue                       # already filled
            if len(future) < days:
                continue                       # not enough future data yet
            future_price = float(future.iloc[days - 1])
            ret          = (future_price - float(pred_price)) / float(pred_price) * 100
            df.at[idx, col_ret] = round(ret, 4)
            if sig == "BULLISH":
                df.at[idx, col_hit] = bool(ret > 0)
            elif sig == "BEARISH":
                df.at[idx, col_hit] = bool(ret < 0)
            # NEUTRAL: no directional judgment
    return df


# ── main ──────────────────────────────────────────────────────────────────────
def fetch_predictions(today_str=None):
    today_str = today_str or date.today().isoformat()

    # Load existing
    if PRED_FILE.exists():
        existing = pd.read_csv(PRED_FILE)
        existing["date"] = pd.to_datetime(existing["date"]).dt.strftime("%Y-%m-%d")
    else:
        existing = pd.DataFrame()

    # Add today's predictions if not already present
    already = (not existing.empty and (existing["date"] == today_str).any())
    new_rows = []
    if not already:
        print(f"  Generating predictions for {today_str}…")
        for ticker in config.TICKERS:
            r = _compute_row(ticker, today_str)
            if r:
                new_rows.append(r)
        print(f"  {len(new_rows)} predictions written")
    else:
        print(f"  Predictions for {today_str} already exist — skipping write")

    all_df = (
        pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
        if new_rows else existing.copy()
    )

    if all_df.empty:
        print("  No prediction data.")
        return

    all_df["date"] = pd.to_datetime(all_df["date"]).dt.strftime("%Y-%m-%d")
    all_df = _fill_actuals(all_df)
    all_df = all_df.sort_values(["date", "ticker"]).reset_index(drop=True)
    all_df.to_csv(PRED_FILE, index=False)
    print(f"  predictions.csv: {len(all_df)} total rows")


if __name__ == "__main__":
    fetch_predictions()
