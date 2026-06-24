"""
fetch_macro_events.py
Fetches upcoming Fed (FOMC) meeting dates and CPI release dates from public
US government websites. No API key required.
Sources:
  - FOMC dates: federalreserve.gov/monetarypolicy/fomccalendars.htm
  - CPI dates:  bls.gov/schedule/news_release/cpi.htm
Saves: data/macro_events.csv
Columns: event_date, event_type, description, days_until
"""

import re
import urllib.request
from datetime import date, datetime
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS  = {"User-Agent": "AltDataSignalTracker/1.0 ellaktran@gmail.com"}
MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="replace")


def _fetch_fomc_dates() -> list[dict]:
    """Parse FOMC meeting dates from the Fed's calendar page."""
    html = _get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    rows = []

    # Find all year section positions using their anchor IDs
    # e.g. <a id="42828">2026 FOMC Meetings</a>
    section_anchors = re.findall(r'<a id="(\d+)">\s*(\d{4})\s+FOMC Meetings\s*</a>', html)
    positions = []
    for anchor_id, yr in section_anchors:
        pos = html.find(f'<a id="{anchor_id}">')
        positions.append((int(yr), pos))
    positions.sort(key=lambda x: x[1])  # sort by position in HTML

    today_year = date.today().year
    for idx, (year, start) in enumerate(positions):
        if year < today_year:
            continue
        # Section ends where next section starts
        end = positions[idx + 1][1] if idx + 1 < len(positions) else start + 60000
        section = html[start:end]

        # Extract all month divs and date divs independently (zip them)
        # Date divs may end with * for tentative dates — strip it
        months_found = re.findall(
            r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>', section
        )
        dates_found = re.findall(
            r'fomc-meeting__date[^>]*>([\d\s–\-]+)\*?<', section
        )

        for month_str, day_range in zip(months_found, dates_found):
            month_str = month_str.strip().lower()
            month_num = MONTH_MAP.get(month_str[:3])
            if not month_num:
                continue
            # day_range like "27-28" or "17-18"; take the last (decision) day
            day_nums = re.findall(r'\d+', day_range)
            if not day_nums:
                continue
            decision_day = int(day_nums[-1])
            try:
                event_date = date(year, month_num, decision_day)
            except ValueError:
                continue
            rows.append({
                "event_date":  event_date,
                "event_type":  "FOMC Meeting",
                "description": (
                    f"Fed FOMC meeting decision day "
                    f"({month_str.capitalize()} {year})"
                ),
            })
    return rows


def _fetch_cpi_dates() -> list[dict]:
    """Parse CPI release dates from the BLS schedule page."""
    html  = _get("https://www.bls.gov/schedule/news_release/cpi.htm")
    rows  = []

    tr_texts = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in tr_texts:
        text = re.sub(r'<[^>]+>', ' ', row)
        text = re.sub(r'\s+', ' ', text).strip()

        # Match e.g. "January 2026 Feb. 13, 2026 08:30 AM"
        m = re.search(
            r'(\w+ \d{4})\s+(\w+\.?\s+\d{1,2},\s+\d{4})',
            text
        )
        if not m:
            continue
        release_str = m.group(2).strip().replace(".", "")
        for fmt in ("%b %d, %Y", "%B %d, %Y"):
            try:
                event_date = datetime.strptime(release_str, fmt).date()
                break
            except ValueError:
                continue
        else:
            continue

        data_period = m.group(1)
        rows.append({
            "event_date":  event_date,
            "event_type":  "CPI Release",
            "description": f"BLS CPI release for {data_period}",
        })
    return rows


def fetch_macro_events():
    print("Fetching FOMC meeting dates from Federal Reserve...", end=" ", flush=True)
    try:
        fomc = _fetch_fomc_dates()
        print(f"{len(fomc)} dates found")
    except Exception as e:
        print(f"FAILED: {e}")
        fomc = []

    print("Fetching CPI release dates from BLS...", end=" ", flush=True)
    try:
        cpi = _fetch_cpi_dates()
        print(f"{len(cpi)} dates found")
    except Exception as e:
        print(f"FAILED: {e}")
        cpi = []

    all_events = fomc + cpi
    if not all_events:
        print("No macro events found — check page structure")
        return False

    df = pd.DataFrame(all_events)
    df["event_date"] = pd.to_datetime(df["event_date"])
    df = df.sort_values("event_date")
    today = date.today()
    df["days_until"] = (df["event_date"].dt.date - today).apply(lambda x: x.days)

    out = DATA_DIR / "macro_events.csv"
    df.to_csv(out, index=False)

    upcoming = df[df["days_until"] >= 0].head(6)
    print(f"\nSaved {len(df)} events to macro_events.csv")
    print("Next events:")
    for _, r in upcoming.iterrows():
        print(f"  {r['event_date'].date()}  ({r['days_until']:+d}d)  "
              f"{r['event_type']}: {r['description']}")
    return True


if __name__ == "__main__":
    fetch_macro_events()
