"""
correlations.py
Computes lead/lag cross-correlations between each alt-data signal and
daily stock returns, for lags −3 to +3 days.

Signals analyzed:
  - wikipedia_views   (Wikipedia daily page views)
  - google_trends     (Google Trends search interest)
  - stocktwits_sent   (StockTwits net sentiment)
  - news_sent         (Yahoo Finance news avg sentiment)

Output: data/correlations_TICKER.csv
  Columns: ticker, signal, lag, correlation, n_obs
  lag > 0 means the signal LEADS the return by that many days.
  lag < 0 means the signal LAGS the return (return leads signal).
"""

from pathlib import Path
import numpy as np
import pandas as pd
import config

DATA_DIR = Path(__file__).parent / "data"


def _load_prices(ticker) -> pd.Series:
    p = DATA_DIR / f"prices_{ticker}.csv"
    if not p.exists():
        return pd.Series(dtype=float)
    df = pd.read_csv(p, parse_dates=["date"], index_col="date")
    col = "close_price" if "close_price" in df.columns else df.columns[0]
    prices = df[col].dropna().sort_index()
    returns = prices.pct_change().dropna()
    return returns


def _load_signal(ticker, signal_name) -> pd.Series:
    if signal_name == "wikipedia_views":
        p = DATA_DIR / f"wikipedia_{ticker}.csv"
        if not p.exists():
            return pd.Series(dtype=float)
        df = pd.read_csv(p, parse_dates=["date"], index_col="date")
        s = df["page_views"].dropna().sort_index()
        # Log-transform to dampen viral spikes; then normalize
        return np.log1p(s).rename("wikipedia_views")

    if signal_name == "google_trends":
        p = DATA_DIR / f"trends_{ticker}.csv"
        if not p.exists():
            return pd.Series(dtype=float)
        df = pd.read_csv(p, parse_dates=["date"], index_col="date")
        col = df.mean().idxmax()
        return df[col].dropna().sort_index().rename("google_trends")

    if signal_name == "stocktwits_sent":
        p = DATA_DIR / f"stocktwits_{ticker}.csv"
        if not p.exists():
            return pd.Series(dtype=float)
        df = pd.read_csv(p, parse_dates=["date"], index_col="date")
        if "net_sentiment" not in df.columns:
            return pd.Series(dtype=float)
        return df["net_sentiment"].dropna().sort_index().rename("stocktwits_sent")

    if signal_name == "news_sent":
        p = DATA_DIR / f"news_{ticker}.csv"
        if not p.exists():
            return pd.Series(dtype=float)
        df = pd.read_csv(p, parse_dates=["date"], index_col="date")
        if "avg_sentiment" not in df.columns:
            return pd.Series(dtype=float)
        return df["avg_sentiment"].dropna().sort_index().rename("news_sent")

    return pd.Series(dtype=float)


def _cross_corr(signal: pd.Series, returns: pd.Series, lag: int):
    """
    Correlation of signal[t] with returns[t + lag].
    lag > 0  → signal leads returns (signal comes before the price move).
    lag < 0  → returns lead signal (price moves first).
    """
    aligned = pd.DataFrame({"signal": signal, "returns": returns}).dropna()
    if len(aligned) < 10:
        return np.nan, 0

    sig = aligned["signal"]
    ret = aligned["returns"].shift(-lag)   # shift returns backward by lag
    combined = pd.concat([sig, ret], axis=1).dropna()
    if len(combined) < 10:
        return np.nan, 0

    corr = combined.iloc[:, 0].corr(combined.iloc[:, 1])
    return corr, len(combined)


SIGNALS = ["wikipedia_views", "google_trends", "stocktwits_sent", "news_sent"]
LAGS    = list(range(-3, 4))   # -3, -2, -1, 0, +1, +2, +3


def compute_correlations():
    all_rows = []

    for ticker in config.TICKERS:
        returns = _load_prices(ticker)
        if returns.empty:
            print(f"  {ticker}: no price data — skipping")
            continue

        for signal_name in SIGNALS:
            signal = _load_signal(ticker, signal_name)
            if signal.empty:
                continue

            for lag in LAGS:
                corr, n = _cross_corr(signal, returns, lag)
                if not np.isnan(corr):
                    all_rows.append({
                        "ticker":      ticker,
                        "signal":      signal_name,
                        "lag":         lag,
                        "correlation": round(corr, 4),
                        "n_obs":       n,
                    })

        print(f"  {ticker}: correlations computed")

    if not all_rows:
        print("  No correlation data — need more price + signal history.")
        return

    df = pd.DataFrame(all_rows)
    out = DATA_DIR / "correlations_all.csv"
    df.to_csv(out, index=False)
    print(f"  Saved {len(df)} rows → {out.name}")


if __name__ == "__main__":
    compute_correlations()
