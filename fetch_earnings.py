"""
fetch_earnings.py
Pulls earnings dates, EPS estimates, actuals, and analyst revenue estimates
for all tracked tickers using Yahoo Finance (yfinance).
Saves: data/earnings_TICKER.csv
Columns: earnings_date, eps_estimate, eps_actual, surprise_pct,
         revenue_estimate_low, revenue_estimate_high, revenue_estimate_avg,
         days_until_earnings
"""

import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("yfinance is required: pip3 install yfinance")

import config

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def fetch_earnings_for_ticker(ticker: str) -> bool:
    try:
        t = yf.Ticker(ticker)
        cal      = t.calendar        # dict with next earnings date + estimates
        hist     = t.earnings_dates  # DataFrame of historical + upcoming dates
    except Exception as e:
        print(f"  {ticker}: yfinance error — {e}")
        return False

    rows = []

    # Historical and upcoming earnings dates from earnings_dates DataFrame
    if hist is not None and not hist.empty:
        hist = hist.reset_index()
        hist.columns = [c.strip() for c in hist.columns]
        date_col = hist.columns[0]  # 'Earnings Date'
        for _, row in hist.iterrows():
            try:
                ed = pd.to_datetime(row[date_col]).date()
            except Exception:
                continue
            eps_est = row.get("EPS Estimate") if "EPS Estimate" in row else None
            eps_act = row.get("Reported EPS") if "Reported EPS" in row else None
            surp    = row.get("Surprise(%)") if "Surprise(%)" in row else None

            import math
            def _safe(v):
                try:
                    return None if (v is None or (isinstance(v, float) and math.isnan(v))) else v
                except Exception:
                    return None

            rows.append({
                "earnings_date":           str(ed),
                "eps_estimate":            _safe(eps_est),
                "eps_actual":              _safe(eps_act),
                "surprise_pct":            _safe(surp),
                "revenue_estimate_low":    None,
                "revenue_estimate_high":   None,
                "revenue_estimate_avg":    None,
            })

    # Overlay next-earnings revenue estimates from calendar (more detailed)
    if cal and "Earnings Date" in cal:
        next_dates = cal["Earnings Date"]
        if not isinstance(next_dates, list):
            next_dates = [next_dates]
        next_date_str = str(next_dates[0]) if next_dates else None

        for r in rows:
            if r["earnings_date"] == next_date_str:
                r["revenue_estimate_low"]  = cal.get("Revenue Low")
                r["revenue_estimate_high"] = cal.get("Revenue High")
                r["revenue_estimate_avg"]  = cal.get("Revenue Average")
                r["eps_estimate"]          = r["eps_estimate"] or cal.get("Earnings Average")
                break

    if not rows:
        print(f"  {ticker}: no earnings data available")
        return False

    df = pd.DataFrame(rows)
    df["earnings_date"] = pd.to_datetime(df["earnings_date"])
    df = df.sort_values("earnings_date", ascending=False)

    today = date.today()
    df["days_until_earnings"] = (df["earnings_date"].dt.date - today).apply(lambda x: x.days)

    out = DATA_DIR / f"earnings_{ticker}.csv"
    df.to_csv(out, index=False)

    next_row = df[df["days_until_earnings"] >= 0]
    if not next_row.empty:
        nr    = next_row.iloc[-1]   # nearest upcoming
        d_str = str(nr["earnings_date"].date())
        days  = int(nr["days_until_earnings"])
        eps_e = nr["eps_estimate"]
        print(f"  {ticker}: next earnings {d_str} (in {days} days)  "
              f"EPS est={eps_e}  total rows={len(df)}")
    else:
        print(f"  {ticker}: {len(df)} historical rows, no upcoming date found")
    return True


def fetch_earnings():
    print(f"Fetching earnings calendar for {len(config.TICKERS)} tickers...\n")
    ok = fail = 0
    for ticker in config.TICKERS:
        if fetch_earnings_for_ticker(ticker):
            ok += 1
        else:
            fail += 1
        time.sleep(0.5)
    print(f"\n--- Earnings summary: {ok} OK, {fail} failed ---")


if __name__ == "__main__":
    fetch_earnings()
