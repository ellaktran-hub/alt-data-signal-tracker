"""
fetch_trends.py
Pulls 90 days of Google Trends interest data for all tickers in config.TICKERS.
Score 0–100: 100 = peak search interest for that term over the period.
Adds a delay between tickers to avoid Google rate limiting.
No credentials required.
"""

import pandas as pd
from pytrends.request import TrendReq
from pathlib import Path
from datetime import date, timedelta
import time
import config


def fetch_trends_for_ticker(pytrends, ticker, timeframe):
    company  = config.COMPANIES.get(ticker, ticker)
    # Deduplicate: pytrends errors if both keywords are identical
    keywords = [ticker, company] if company.lower() != ticker.lower() else [ticker]

    try:
        pytrends.build_payload(keywords, timeframe=timeframe, geo="US")
        time.sleep(2)   # pause after every request — Google rate-limits aggressively
        df = pytrends.interest_over_time()
    except Exception as e:
        msg = str(e)
        if "429" in msg or "Too Many Requests" in msg or "response" in msg.lower():
            print(f"  [{ticker}] Rate limited — waiting 30s...")
            time.sleep(30)
            try:
                pytrends.build_payload(keywords, timeframe=timeframe, geo="US")
                df = pytrends.interest_over_time()
            except Exception as e2:
                print(f"  [{ticker}] Retry failed: {e2}")
                return False
        else:
            print(f"  [{ticker}] Error: {e}")
            return False

    if df.empty:
        print(f"  [{ticker}] No data returned")
        return False

    if "isPartial" in df.columns:
        df = df.drop(columns=["isPartial"])

    df.index = pd.to_datetime(df.index).date
    df.index.name = "date"
    df.columns = [f"trends_{kw.lower().replace(' ', '_')}" for kw in df.columns]

    out_path = Path(__file__).parent / "data" / f"trends_{ticker}.csv"
    df.to_csv(out_path)
    print(f"  [{ticker}] {len(df)} rows saved")
    return True


def fetch_trends():
    end       = date.today()
    start     = end - timedelta(days=config.LOOKBACK_DAYS)
    timeframe = f"{start} {end}"

    print(f"Fetching Google Trends for {len(config.TICKERS)} tickers ({start} to {end})...")
    print("  (Note: 2s delay between tickers to avoid rate limiting)\n")

    pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
    results  = {}

    for ticker in config.TICKERS:
        ok = fetch_trends_for_ticker(pytrends, ticker, timeframe)
        results[ticker] = "OK" if ok else "FAILED"

    print("\n--- Google Trends fetch summary ---")
    for ticker, status in results.items():
        print(f"  {status:6s}  {ticker}")


if __name__ == "__main__":
    fetch_trends()
