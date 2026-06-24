"""
fetch_shortinterest.py
Pulls short interest data for all tracked tickers using Yahoo Finance.
FINRA reports short interest twice monthly; yfinance caches the most recent
report in Ticker.info. We accumulate one row per run (de-duped by date).
Saves: data/shortinterest_TICKER.csv
Columns: date, shares_short, short_ratio, short_pct_float, shares_float
"""

import time
from datetime import date
from pathlib import Path

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("yfinance is required: pip3 install yfinance")

import config

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

INFO_KEYS = {
    "sharesShort":          "shares_short",
    "shortRatio":           "short_ratio",      # days-to-cover
    "shortPercentOfFloat":  "short_pct_float",  # 0.0–1.0
    "floatShares":          "shares_float",
}


def fetch_shortinterest_for_ticker(ticker: str) -> bool:
    try:
        info = yf.Ticker(ticker).info
    except Exception as e:
        print(f"  {ticker}: failed to get info — {e}")
        return False

    row = {"date": pd.Timestamp(date.today())}
    has_data = False
    for yf_key, col in INFO_KEYS.items():
        val = info.get(yf_key)
        row[col] = val
        if val is not None:
            has_data = True

    if not has_data:
        print(f"  {ticker}: no short interest data in info dict")
        return False

    # Format for display
    pct = row.get("short_pct_float")
    pct_str = f"{pct*100:.1f}%" if pct else "—"
    ratio   = row.get("short_ratio")
    print(f"  {ticker}: short_pct={pct_str}  days_to_cover={ratio}  "
          f"shares_short={row.get('shares_short'):,}" if row.get('shares_short') else
          f"  {ticker}: short_pct={pct_str}  days_to_cover={ratio}")

    new_row = pd.DataFrame([row])
    out = DATA_DIR / f"shortinterest_{ticker}.csv"
    if out.exists():
        existing = pd.read_csv(out, parse_dates=["date"])
        combined = pd.concat([existing, new_row], ignore_index=True)
        combined = combined.drop_duplicates(subset=["date"], keep="last")
        combined = combined.sort_values("date")
    else:
        combined = new_row

    combined.to_csv(out, index=False)
    return True


def fetch_shortinterest():
    print(f"Fetching short interest data for {len(config.TICKERS)} tickers...\n")
    ok = fail = 0
    for ticker in config.TICKERS:
        if fetch_shortinterest_for_ticker(ticker):
            ok += 1
        else:
            fail += 1
        time.sleep(0.4)
    print(f"\n--- Short interest summary: {ok} OK, {fail} failed ---")


if __name__ == "__main__":
    fetch_shortinterest()
