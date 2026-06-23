"""
fetch_price.py
Pulls 90 days of daily closing prices for all tickers in config.TICKERS
from Yahoo Finance and saves one CSV per ticker to data/.
"""

import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
import time
import config


def fetch_price_for_ticker(ticker):
    end   = date.today()
    start = end - timedelta(days=config.LOOKBACK_DAYS)

    try:
        df = yf.Ticker(ticker).history(start=str(start), end=str(end))
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    if df.empty:
        print(f"  {ticker}: no data returned (check ticker symbol)")
        return False

    df = df[["Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index).date
    df.index.name = "date"
    df.columns = ["close_price", "volume"]

    out_path = Path(__file__).parent / "data" / f"prices_{ticker}.csv"
    df.to_csv(out_path)
    print(f"  {ticker}: {len(df)} rows saved  (latest close: {df['close_price'].iloc[-1]:.2f})")
    return True


def fetch_price():
    end   = date.today()
    start = end - timedelta(days=config.LOOKBACK_DAYS)
    print(f"Fetching prices for {len(config.TICKERS)} tickers ({start} to {end})...\n")

    results = {}
    for ticker in config.TICKERS:
        results[ticker] = "OK" if fetch_price_for_ticker(ticker) else "FAILED"
        time.sleep(0.3)

    print("\n--- Price fetch summary ---")
    for ticker, status in results.items():
        print(f"  {status:6s}  {ticker}")


if __name__ == "__main__":
    fetch_price()
