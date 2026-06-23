"""
fetch_reddit.py
Fetches recent Reddit posts mentioning the configured stock from public
subreddits using Reddit's public JSON API — no credentials required.
Scores sentiment with VADER and saves a daily summary to data/.
"""

import requests
import pandas as pd
from datetime import date, timedelta, datetime
from pathlib import Path
from collections import defaultdict
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import time
import config

SUBREDDITS = ["stocks", "investing", "wallstreetbets", "StockMarket"]
HEADERS = {"User-Agent": "AltDataResearch/0.1 (academic project)"}


def fetch_posts(subreddit, query, days_back):
    """Pull up to 100 recent posts matching query from one subreddit."""
    url = (
        f"https://www.reddit.com/r/{subreddit}/search.json"
        f"?q={query}&sort=new&limit=100&t=month&restrict_sr=1"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        posts = r.json()["data"]["children"]
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        results = []
        for p in posts:
            d = p["data"]
            created = datetime.utcfromtimestamp(d["created_utc"])
            if created >= cutoff:
                results.append({
                    "title": d["title"],
                    "score": d["score"],        # Reddit upvotes
                    "created": created.date(),
                })
        return results
    except Exception as e:
        print(f"  Warning: could not fetch r/{subreddit} — {e}")
        return []


def fetch_reddit():
    analyzer = SentimentIntensityAnalyzer()
    query    = f"{config.TICKER} {config.COMPANY_NAME}"
    days     = config.LOOKBACK_DAYS

    print(f"Fetching Reddit posts for '{query}' across {len(SUBREDDITS)} subreddits...")

    all_posts = []
    for sub in SUBREDDITS:
        posts = fetch_posts(sub, query, days)
        print(f"  r/{sub}: {len(posts)} posts found")
        all_posts.extend(posts)
        time.sleep(1)   # be polite — avoid rate limiting

    if not all_posts:
        print("ERROR: No posts found. Try adjusting TICKER or COMPANY_NAME in config.py.")
        return

    # Score each post title for sentiment
    daily = defaultdict(lambda: {"post_count": 0, "sentiment_sum": 0.0})
    for p in all_posts:
        day = p["created"]
        sentiment = analyzer.polarity_scores(p["title"])["compound"]  # -1 to +1
        daily[day]["post_count"]    += 1
        daily[day]["sentiment_sum"] += sentiment

    # Build one row per day with average sentiment
    rows = []
    for day, vals in sorted(daily.items()):
        count = vals["post_count"]
        rows.append({
            "date":               day,
            "post_count":         count,
            "avg_sentiment":      round(vals["sentiment_sum"] / count, 4),
        })

    df = pd.DataFrame(rows).set_index("date")

    out_path = Path(__file__).parent / "data" / f"reddit_{config.TICKER}.csv"
    df.to_csv(out_path)
    print(f"\nSaved {len(df)} days of data to {out_path.name}")
    print(df.tail(5))


if __name__ == "__main__":
    fetch_reddit()
