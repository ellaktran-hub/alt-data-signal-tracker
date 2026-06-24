"""
fetch_options.py
Pulls options put/call ratio for all tracked tickers using Yahoo Finance.
For each ticker, sums call volume and put volume across the nearest 4
expiration dates, then calculates put_call_ratio = put_volume / call_volume.
Saves: data/options_TICKER.csv
Columns: date, call_volume, put_volume, put_call_ratio, avg_call_iv, avg_put_iv
"""

import time
from datetime import date
from pathlib import Path

import pandas as pd
import numpy as np

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("yfinance is required: pip3 install yfinance")

import config

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

N_EXPIRIES = 4   # number of nearest expiry dates to aggregate


def fetch_options_for_ticker(ticker: str) -> bool:
    try:
        t = yf.Ticker(ticker)
        exps = t.options          # list of expiry date strings, nearest first
    except Exception as e:
        print(f"  {ticker}: failed to get expiry list — {e}")
        return False

    if not exps:
        print(f"  {ticker}: no options data available")
        return False

    call_vol = 0
    put_vol  = 0
    call_ivs = []
    put_ivs  = []

    for exp in exps[:N_EXPIRIES]:
        try:
            chain = t.option_chain(exp)
        except Exception as e:
            print(f"  {ticker}: chain error for {exp} — {e}")
            continue

        c = chain.calls
        p = chain.puts

        if not c.empty and "volume" in c.columns:
            call_vol += int(c["volume"].fillna(0).sum())
        if not p.empty and "volume" in p.columns:
            put_vol  += int(p["volume"].fillna(0).sum())
        if not c.empty and "impliedVolatility" in c.columns:
            call_ivs.extend(c["impliedVolatility"].dropna().tolist())
        if not p.empty and "impliedVolatility" in p.columns:
            put_ivs.extend(p["impliedVolatility"].dropna().tolist())

    if call_vol == 0 and put_vol == 0:
        print(f"  {ticker}: zero volume — skipping")
        return False

    pcr = round(put_vol / call_vol, 4) if call_vol > 0 else None
    avg_civ = round(float(np.mean(call_ivs)), 4) if call_ivs else None
    avg_piv = round(float(np.mean(put_ivs)),  4) if put_ivs  else None

    today = pd.Timestamp(date.today())
    new_row = pd.DataFrame([{
        "date":           today,
        "call_volume":    call_vol,
        "put_volume":     put_vol,
        "put_call_ratio": pcr,
        "avg_call_iv":    avg_civ,
        "avg_put_iv":     avg_piv,
    }])

    out = DATA_DIR / f"options_{ticker}.csv"
    if out.exists():
        existing = pd.read_csv(out, parse_dates=["date"])
        combined = pd.concat([existing, new_row], ignore_index=True)
        combined = combined.drop_duplicates(subset=["date"], keep="last")
        combined = combined.sort_values("date")
    else:
        combined = new_row

    combined.to_csv(out, index=False)
    print(f"  {ticker}: P/C={pcr}  calls={call_vol:,}  puts={put_vol:,}  "
          f"call_iv={avg_civ}  put_iv={avg_piv}")
    return True


def fetch_options():
    print(f"Fetching options data for {len(config.TICKERS)} tickers...\n")
    ok = fail = skip = 0
    for ticker in config.TICKERS:
        result = fetch_options_for_ticker(ticker)
        if result:
            ok += 1
        else:
            fail += 1
        time.sleep(0.5)
    print(f"\n--- Options summary: {ok} OK, {fail} failed/skipped ---")


if __name__ == "__main__":
    fetch_options()
