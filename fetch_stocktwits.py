"""
fetch_stocktwits.py
Pulls recent StockTwits messages for all tickers in config.TICKERS.
Users label posts Bullish or Bearish — we aggregate into daily scores.
Low-volume tickers may return no data; those are saved as empty CSVs.
No credentials required.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
import time
import config

HEADERS = {"User-Agent": "AltDataResearch/0.1 (academic project)"}
EMPTY_COLS = ["message_count", "bullish_count", "bearish_count", "net_sentiment"]


def fetch_messages(ticker):
    url    = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
    cutoff = datetime.utcnow() - timedelta(days=config.LOOKBACK_DAYS)
    all_messages = []
    params = {"limit": 30}

    for page in range(20):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=10)
            if r.status_code == 429:
                print(f"  [{ticker}] Rate limited — waiting 60s...")
                time.sleep(60)
                continue
            if r.status_code == 404:
                print(f"  [{ticker}] Ticker not found on StockTwits")
                return []
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"  [{ticker}] Request failed: {e}")
            return all_messages

        messages = data.get("messages", [])
        if not messages:
            break

        for m in messages:
            created = datetime.strptime(m["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            if created < cutoff:
                return all_messages

            sentiment = None
            if m.get("entities", {}).get("sentiment"):
                sentiment = m["entities"]["sentiment"].get("basic")

            all_messages.append({"date": created.date(), "sentiment": sentiment})

        cursor = data.get("cursor", {})
        if not cursor.get("more"):
            break
        params["max_id"] = cursor["max"]
        time.sleep(0.5)

    return all_messages


def save_empty(ticker):
    out_path = Path(__file__).parent / "data" / f"stocktwits_{ticker}.csv"
    pd.DataFrame(columns=["date"] + EMPTY_COLS).set_index("date").to_csv(out_path)
    print(f"  [{ticker}] No data — saved empty CSV")


def fetch_stocktwits_for_ticker(ticker):
    messages = fetch_messages(ticker)

    if not messages:
        save_empty(ticker)
        return False

    daily = defaultdict(lambda: {"total": 0, "bullish": 0, "bearish": 0})
    for m in messages:
        day = m["date"]
        daily[day]["total"] += 1
        if m["sentiment"] == "Bullish":
            daily[day]["bullish"] += 1
        elif m["sentiment"] == "Bearish":
            daily[day]["bearish"] += 1

    rows = []
    for day, v in sorted(daily.items()):
        labeled = v["bullish"] + v["bearish"]
        rows.append({
            "date":          day,
            "message_count": v["total"],
            "bullish_count": v["bullish"],
            "bearish_count": v["bearish"],
            "net_sentiment": round((v["bullish"] - v["bearish"]) / labeled * 100, 1) if labeled else 0,
        })

    df = pd.DataFrame(rows).set_index("date")
    out_path = Path(__file__).parent / "data" / f"stocktwits_{ticker}.csv"
    df.to_csv(out_path)
    print(f"  [{ticker}] {len(messages)} messages → {len(df)} days saved")
    return True


def fetch_stocktwits():
    print(f"Fetching StockTwits sentiment for {len(config.TICKERS)} tickers...\n")
    results = {}

    for ticker in config.TICKERS:
        ok = fetch_stocktwits_for_ticker(ticker)
        results[ticker] = "OK" if ok else "EMPTY"
        time.sleep(1)

    print("\n--- StockTwits fetch summary ---")
    for ticker, status in results.items():
        print(f"  {status:6s}  {ticker}")


if __name__ == "__main__":
    fetch_stocktwits()
