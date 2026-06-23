"""
fetch_news.py
Pulls Yahoo Finance news headlines for all tickers in config.TICKERS,
scores each headline with VADER sentiment, and saves a daily summary
per ticker to data/news_TICKER.csv.
No credentials required — uses yfinance's built-in news feed.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import time
import config

analyzer = SentimentIntensityAnalyzer()


def fetch_news_for_ticker(ticker):
    cutoff = datetime.utcnow() - timedelta(days=config.LOOKBACK_DAYS)

    try:
        yf_ticker = yf.Ticker(ticker)
        news_items = yf_ticker.news
    except Exception as e:
        print(f"  ERROR fetching news for {ticker}: {e}")
        return None

    if not news_items:
        print(f"  {ticker}: no news returned")
        return None

    daily = defaultdict(lambda: {"headline_count": 0, "sentiment_sum": 0.0})

    for item in news_items:
        # yfinance now nests everything inside item["content"]
        content = item.get("content", item)

        title = content.get("title", "")
        if not title:
            continue

        # New format uses ISO string; old format used Unix timestamp
        pub_str = content.get("pubDate") or content.get("displayTime", "")
        try:
            pub_date = datetime.strptime(pub_str, "%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            pub_time = content.get("providerPublishTime", 0)
            try:
                pub_date = datetime.utcfromtimestamp(int(pub_time))
            except (ValueError, TypeError, OSError):
                continue

        if pub_date < cutoff:
            continue

        sentiment = analyzer.polarity_scores(title)["compound"]  # -1 to +1
        day = pub_date.date()
        daily[day]["headline_count"]  += 1
        daily[day]["sentiment_sum"]   += sentiment

    if not daily:
        print(f"  {ticker}: no headlines within {config.LOOKBACK_DAYS}-day window")
        return None

    rows = []
    for day, v in sorted(daily.items()):
        count = v["headline_count"]
        rows.append({
            "date":             day,
            "headline_count":   count,
            "avg_sentiment":    round(v["sentiment_sum"] / count, 4),
        })

    df = pd.DataFrame(rows).set_index("date")
    out_path = Path(__file__).parent / "data" / f"news_{ticker}.csv"
    df.to_csv(out_path)
    return df


def fetch_news():
    print(f"Fetching Yahoo Finance news for {len(config.TICKERS)} tickers...\n")
    results = {}

    for ticker in config.TICKERS:
        print(f"[{ticker}]")
        df = fetch_news_for_ticker(ticker)
        if df is not None:
            latest = df.tail(1)
            print(f"  Saved {len(df)} days → last row: {latest.to_dict('records')[0]}")
            results[ticker] = "OK"
        else:
            results[ticker] = "NO DATA"
        time.sleep(0.5)   # avoid hammering Yahoo Finance

    print("\n--- News fetch summary ---")
    for ticker, status in results.items():
        print(f"  {status:8s}  {ticker}")


if __name__ == "__main__":
    fetch_news()
