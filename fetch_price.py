"""
fetch_price.py
Pulls 90 days of daily closing prices + volume for all tickers in config.TICKERS
(plus macro symbols BTC-USD, ETH-USD, ^VIX) from Yahoo Finance.
Adds a volume_anomaly column: 1 when daily volume > 2 std devs above 30-day
rolling average (unusual trading activity), 0 otherwise.
Saves: data/prices_TICKER.csv and data/prices_macro_SYMBOL.csv
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date, timedelta
from pathlib import Path
import time
import config

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Macro context symbols fetched separately (not equity signals)
MACRO_SYMBOLS = ["BTC-USD", "ETH-USD", "^VIX"]


def _add_volume_anomaly(df: pd.DataFrame) -> pd.DataFrame:
    """Add volume_anomaly column: 1 if volume > rolling_mean + 2*rolling_std."""
    if "volume" not in df.columns or len(df) < 5:
        df["volume_anomaly"] = 0
        return df
    roll_mean = df["volume"].rolling(window=30, min_periods=5).mean()
    roll_std  = df["volume"].rolling(window=30, min_periods=5).std()
    df["volume_anomaly"] = (
        (df["volume"] > roll_mean + 2 * roll_std).astype(int)
    )
    return df


def fetch_price_for_ticker(ticker, out_prefix="prices"):
    end   = date.today()
    start = end - timedelta(days=config.LOOKBACK_DAYS)

    try:
        df = yf.Ticker(ticker).history(start=str(start), end=str(end))
    except Exception as e:
        print(f"  ERROR {ticker}: {e}")
        return False

    if df.empty:
        print(f"  {ticker}: no data returned (check ticker symbol)")
        return False

    cols = [c for c in ["Close", "Volume"] if c in df.columns]
    df = df[cols].copy()
    df.index = pd.to_datetime(df.index).date
    df.index.name = "date"
    rename = {"Close": "close_price", "Volume": "volume"}
    df = df.rename(columns={c: rename[c] for c in cols})
    if "volume" not in df.columns:
        df["volume"] = np.nan
    df = _add_volume_anomaly(df)

    safe_name = ticker.replace("^", "")
    out_path = DATA_DIR / f"{out_prefix}_{safe_name}.csv"
    df.to_csv(out_path)

    anomalies = int(df["volume_anomaly"].sum())
    print(f"  {ticker}: {len(df)} rows  close={df['close_price'].iloc[-1]:.2f}"
          f"  vol_anomalies={anomalies}")
    return True


def fetch_price():
    end   = date.today()
    start = end - timedelta(days=config.LOOKBACK_DAYS)
    print(f"Fetching prices for {len(config.TICKERS)} tickers ({start} to {end})...\n")

    results = {}
    for ticker in config.TICKERS:
        results[ticker] = "OK" if fetch_price_for_ticker(ticker) else "FAILED"
        time.sleep(0.3)

    print(f"\nFetching macro prices: {', '.join(MACRO_SYMBOLS)}\n")
    for sym in MACRO_SYMBOLS:
        fetch_price_for_ticker(sym, out_prefix="prices_macro")
        time.sleep(0.3)

    print("\n--- Price fetch summary ---")
    for ticker, status in results.items():
        print(f"  {status:6s}  {ticker}")


if __name__ == "__main__":
    fetch_price()
