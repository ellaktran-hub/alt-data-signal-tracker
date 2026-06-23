"""
fetch_wikipedia.py
Pulls 91-day daily Wikipedia page-view counts for all tracked tickers via
the free Wikimedia REST API (no credentials required).
Saves: data/wikipedia_TICKER.csv  with columns: date, page_views
"""

import time
import urllib.request
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

import config

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

BASE_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
    "/en.wikipedia/all-access/all-agents/{article}/daily/{start}/{end}"
)

HEADERS = {
    "User-Agent": "AltDataSignalTracker/1.0 (ellaktran@gmail.com)",
    "Accept": "application/json",
}


def _fetch_views(article: str, start: date, end: date) -> pd.Series:
    url = BASE_URL.format(
        article=article,
        start=start.strftime("%Y%m%d"),
        end=end.strftime("%Y%m%d"),
    )
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    rows = []
    for item in data.get("items", []):
        ts = item.get("timestamp", "")
        views = item.get("views", 0)
        try:
            d = date(int(ts[:4]), int(ts[4:6]), int(ts[6:8]))
            rows.append((d, views))
        except (ValueError, IndexError):
            continue
    if not rows:
        return pd.Series(dtype=float, name="page_views")
    s = pd.Series({r[0]: r[1] for r in rows}, name="page_views")
    s.index.name = "date"
    return s


def fetch_wikipedia():
    end   = date.today() - timedelta(days=1)   # yesterday (data lags ~1 day)
    start = end - timedelta(days=config.LOOKBACK_DAYS)

    for ticker in config.TICKERS:
        article = config.WIKI_ARTICLES.get(ticker)
        if not article:
            print(f"  {ticker}: no Wikipedia article — skipping")
            continue

        out = DATA_DIR / f"wikipedia_{ticker}.csv"
        for attempt in range(3):
            try:
                views = _fetch_views(article, start, end)
                if views.empty:
                    print(f"  {ticker}: no data returned")
                    break
                df = views.reset_index()
                df.columns = ["date", "page_views"]
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date")
                df.to_csv(out, index=False)
                print(f"  {ticker}: {len(df)} days saved  ({df['page_views'].max():,.0f} max daily views)")
                break
            except Exception as exc:
                wait = 2 ** attempt
                print(f"  {ticker}: attempt {attempt+1} failed — {exc}  (retrying in {wait}s)")
                time.sleep(wait)
        else:
            print(f"  {ticker}: all retries exhausted — skipping")

        time.sleep(0.3)   # polite rate limit: ~3 req/s


if __name__ == "__main__":
    fetch_wikipedia()
