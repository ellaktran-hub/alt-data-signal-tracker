"""
run_pipeline.py
Runs all data fetchers in sequence, logs results, then pushes fresh
CSV files to GitHub so the live Streamlit dashboard updates automatically.

Post-run automation (all in this file):
  - Health alert email  : sent on step failures or empty price CSVs
  - Daily summary email : top 5 bullish + top 5 bearish tickers
  - Signal flip alert   : NEUTRAL -> BULLISH or BEARISH
  - Price alert         : >5% single-day move on any ticker
  - Weekly backup       : Sundays only — zip data/ -> backups/YYYY-MM-DD.zip
  - Pipeline log CSV    : data/pipeline_log.csv (date, tickers, errors, runtime)

Usage: python3 run_pipeline.py
"""

import csv
import json
import subprocess
import sys
import time
import traceback
import zipfile
from datetime import datetime, date
from pathlib import Path

import config
from notifier import (
    send_health_alert,
    send_daily_summary,
    send_signal_flip_alerts,
    send_price_alerts,
)

PROJECT_DIR       = Path(__file__).parent
DATA_DIR          = PROJECT_DIR / "data"
LOG_PATH          = DATA_DIR / "pipeline_log.txt"
LOG_CSV_PATH      = DATA_DIR / "pipeline_log.csv"
TOKEN_FILE        = PROJECT_DIR / ".github_token"
PREV_SIGNALS_FILE = DATA_DIR / "previous_signals.json"
BACKUP_DIR        = PROJECT_DIR / "backups"
GITHUB_REPO       = "https://github.com/ellaktran-hub/alt-data-signal-tracker.git"


def log(msg):
    line = "[{}] {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def git_push():
    """Stage data/ CSVs, commit, and push to GitHub to update the live dashboard."""
    if not TOKEN_FILE.exists():
        log("Skipping GitHub push — no .github_token file found in project/.")
        log("To enable auto-push, paste your GitHub token into project/.github_token")
        return False

    token = TOKEN_FILE.read_text().strip()
    if not token or token.startswith("PASTE_"):
        log("Skipping GitHub push — .github_token contains placeholder text, not a real token.")
        return False

    try:
        subprocess.run(
            ["git", "add", "data/"],
            cwd=str(PROJECT_DIR), check=True, capture_output=True,
        )

        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(PROJECT_DIR),
        )
        if diff.returncode == 0:
            log("GitHub push skipped — no changes in data/ since last push.")
            return True

        subprocess.run(
            ["git", "commit", "-m", "data: pipeline update {}".format(date.today())],
            cwd=str(PROJECT_DIR), check=True, capture_output=True,
        )

        push_url = "https://{}@github.com/ellaktran-hub/alt-data-signal-tracker.git".format(token)
        result = subprocess.run(
            ["git", "push", push_url, "main"],
            cwd=str(PROJECT_DIR), capture_output=True, text=True,
        )
        if result.returncode == 0:
            log("GitHub push successful — live dashboard will update within ~60 seconds.")
            return True
        else:
            err = result.stderr.replace(token, "***")
            log("GitHub push failed: " + err.strip())
            return False

    except subprocess.CalledProcessError as exc:
        log("GitHub push failed: " + str(exc))
        return False


# ---------------------------------------------------------------------------
# Composite signal computation (mirrors dashboard logic)
# ---------------------------------------------------------------------------

def _compute_signal_for_ticker(ticker):
    """
    Read latest CSV rows and compute composite score for one ticker.
    Score >= +2 -> BULLISH, <= -2 -> BEARISH, else NEUTRAL.
    Returns (signal_str, score_int, detail_str).
    """
    try:
        import pandas as pd
    except ImportError:
        return ("NEUTRAL", 0, "pandas unavailable")

    score = 0
    parts = []

    # --- Price: daily return ---
    try:
        path = DATA_DIR / "prices_{}.csv".format(ticker)
        if path.exists():
            df = pd.read_csv(path)
            if len(df) >= 2:
                prev = df["close_price"].iloc[-2]
                curr = df["close_price"].iloc[-1]
                if prev > 0:
                    ret = (curr - prev) / prev
                    if ret > 0.005:
                        score += 1
                        parts.append("price+{:.1f}%".format(ret * 100))
                    elif ret < -0.005:
                        score -= 1
                        parts.append("price{:.1f}%".format(ret * 100))
    except Exception:
        pass

    # --- StockTwits: bullish% ---
    try:
        path = DATA_DIR / "stocktwits_{}.csv".format(ticker)
        if path.exists():
            df = pd.read_csv(path)
            df = df[df["message_count"] > 0]
            if not df.empty:
                row = df.iloc[-1]
                bullish_pct = row["bullish_count"] / row["message_count"] * 100
                if bullish_pct > 55:
                    score += 1
                    parts.append("twits+{:.0f}%".format(bullish_pct))
                elif bullish_pct < 40:
                    score -= 1
                    parts.append("twits{:.0f}%".format(bullish_pct))
    except Exception:
        pass

    # --- News: avg_sentiment (raw VADER -1 to +1) ---
    try:
        path = DATA_DIR / "news_{}.csv".format(ticker)
        if path.exists():
            df = pd.read_csv(path)
            if not df.empty:
                sent = float(df.iloc[-1]["avg_sentiment"])
                if sent > 0.10:
                    score += 1
                    parts.append("news+{:.2f}".format(sent))
                elif sent < -0.10:
                    score -= 1
                    parts.append("news{:.2f}".format(sent))
    except Exception:
        pass

    # --- Google Trends: today vs 7-day average ---
    try:
        path = DATA_DIR / "trends_{}.csv".format(ticker)
        if path.exists():
            df = pd.read_csv(path, index_col=0)
            num_cols = [c for c in df.columns if c != "date"]
            if num_cols and len(df) >= 2:
                df["_mean"] = df[num_cols].mean(axis=1)
                today_val = df["_mean"].iloc[-1]
                history   = df["_mean"].iloc[-8:-1] if len(df) >= 8 else df["_mean"].iloc[:-1]
                week_avg  = history.mean()
                if week_avg > 0:
                    pct_diff = (today_val - week_avg) / week_avg
                    if pct_diff > 0.10:
                        score += 1
                        parts.append("trends+{:.0f}%".format(pct_diff * 100))
                    elif pct_diff < -0.10:
                        score -= 1
                        parts.append("trends{:.0f}%".format(pct_diff * 100))
    except Exception:
        pass

    if score >= 2:
        signal = "BULLISH"
    elif score <= -2:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    detail = ", ".join(parts) if parts else "no strong signals"
    return (signal, score, detail)


def compute_all_signals():
    """Return {ticker: {"signal": str, "score": int, "detail": str}} for all tickers."""
    results = {}
    for ticker in config.TICKERS:
        signal, score, detail = _compute_signal_for_ticker(ticker)
        results[ticker] = {"signal": signal, "score": score, "detail": detail}
    return results


def load_previous_signals():
    """Load signal strings from the previous run. Returns {} on first run."""
    if PREV_SIGNALS_FILE.exists():
        try:
            return json.loads(PREV_SIGNALS_FILE.read_text())
        except Exception:
            pass
    return {}


def save_signals(signals):
    """Persist current signals so next run can detect flips."""
    try:
        snapshot = {t: v["signal"] for t, v in signals.items()}
        PREV_SIGNALS_FILE.write_text(json.dumps(snapshot))
    except Exception as exc:
        log("Could not save signal snapshot: " + str(exc))


# ---------------------------------------------------------------------------
# Price alert
# ---------------------------------------------------------------------------

def check_price_alerts():
    """Return list of (ticker, pct_change, price) for daily moves > 5%."""
    try:
        import pandas as pd
    except ImportError:
        return []
    movers = []
    for ticker in config.TICKERS:
        try:
            path = DATA_DIR / "prices_{}.csv".format(ticker)
            if not path.exists():
                continue
            df = pd.read_csv(path)
            if len(df) < 2:
                continue
            prev = df["close_price"].iloc[-2]
            curr = df["close_price"].iloc[-1]
            if prev <= 0:
                continue
            pct = (curr - prev) / prev * 100
            if abs(pct) > 5.0:
                movers.append((ticker, pct, curr))
        except Exception:
            pass
    return sorted(movers, key=lambda x: abs(x[1]), reverse=True)


# ---------------------------------------------------------------------------
# Empty data check
# ---------------------------------------------------------------------------

def check_empty_data():
    """Spot-check pinned tickers' price CSVs. Return list of problem strings."""
    try:
        import pandas as pd
    except ImportError:
        return []
    problems = []
    for ticker in config.PINNED_TICKERS:
        path = DATA_DIR / "prices_{}.csv".format(ticker)
        try:
            if not path.exists():
                problems.append("prices_{}.csv missing".format(ticker))
                continue
            df = pd.read_csv(path)
            if df.empty:
                problems.append("prices_{}.csv has no rows".format(ticker))
        except Exception:
            problems.append("prices_{}.csv unreadable".format(ticker))
    return problems


# ---------------------------------------------------------------------------
# Weekly backup
# ---------------------------------------------------------------------------

def weekly_backup():
    """Every Sunday: zip all CSVs in data/ into backups/YYYY-MM-DD.zip."""
    if date.today().weekday() != 6:  # 0=Monday ... 6=Sunday
        return
    BACKUP_DIR.mkdir(exist_ok=True)
    zip_path = BACKUP_DIR / "{}.zip".format(date.today())
    if zip_path.exists():
        log("Weekly backup: archive already exists for today, skipping.")
        return
    try:
        file_count = 0
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for csv_file in sorted(DATA_DIR.glob("*.csv")):
                zf.write(str(csv_file), csv_file.name)
                file_count += 1
        size_mb = zip_path.stat().st_size / 1_048_576
        log("Weekly backup: {} files -> backups/{} ({:.1f} MB)".format(
            file_count, zip_path.name, size_mb))
    except Exception as exc:
        log("Weekly backup FAILED: " + str(exc))


# ---------------------------------------------------------------------------
# Pipeline log CSV
# ---------------------------------------------------------------------------

def append_pipeline_log_csv(run_date, tickers_updated, error_count, runtime_seconds):
    """Append one summary row to data/pipeline_log.csv."""
    write_header = not LOG_CSV_PATH.exists()
    try:
        with open(str(LOG_CSV_PATH), "a", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(["date", "tickers_updated", "errors", "runtime_seconds"])
            writer.writerow([run_date, tickers_updated, error_count, round(runtime_seconds, 1)])
    except Exception as exc:
        log("Could not write pipeline_log.csv: " + str(exc))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    start_time = time.time()
    run_date   = str(date.today())

    log("========== Pipeline run started | tickers: {} ==========".format(
        ", ".join(config.TICKERS)))

    steps = [
        ("Stock prices + volume anomaly (Yahoo Finance)", "fetch_price",         "fetch_price"),
        ("Sentiment (StockTwits)",                        "fetch_stocktwits",    "fetch_stocktwits"),
        ("Search interest (Google Trends)",               "fetch_trends",        "fetch_trends"),
        ("News headlines (Yahoo Finance)",                "fetch_news",          "fetch_news"),
        ("Wikipedia page views",                          "fetch_wikipedia",     "fetch_wikipedia"),
        ("Options put/call ratio (Yahoo Finance)",        "fetch_options",       "fetch_options"),
        ("Short interest (Yahoo Finance)",                "fetch_shortinterest", "fetch_shortinterest"),
        ("Insider transactions (SEC EDGAR Form 4)",       "fetch_insider",       "fetch_insider"),
        ("Earnings calendar (Yahoo Finance)",             "fetch_earnings",      "fetch_earnings"),
        ("Macro events (Fed + BLS)",                      "fetch_macro_events",  "fetch_macro_events"),
        ("Lead/lag correlations",                         "correlations",        "compute_correlations"),
        ("Daily predictions + fill actuals",              "fetch_predictions",   "fetch_predictions"),
    ]

    results = {}
    for label, module, fn in steps:
        log("Starting: " + label)
        try:
            mod = __import__(module)
            getattr(mod, fn)()
            log("OK: " + label)
            results[label] = "OK"
        except Exception:
            log("FAILED: " + label)
            log(traceback.format_exc())
            results[label] = "FAILED"

    log("========== Pipeline summary ==========")
    failed_steps = []
    for label, status in results.items():
        log("  {:<6}  {}".format(status, label))
        if status != "OK":
            failed_steps.append(label)

    all_ok = len(failed_steps) == 0
    log("Pipeline finished." if all_ok else "Pipeline finished with errors — check log above.")

    # Push fresh data to GitHub (even on partial failures — good data still gets pushed)
    log("========== GitHub push ==========")
    git_push()

    log("========== Post-run tasks ==========")

    # 1. Health alert email
    empty_data = check_empty_data()
    if failed_steps or empty_data:
        log("Sending health alert email...")
        send_health_alert(failed_steps, empty_data)
    else:
        log("Health check: all good — no alert sent.")

    # 2. Compute composite signals for all tickers
    log("Computing composite signals...")
    signals = compute_all_signals()

    # 3. Daily summary email (top 5 bullish + top 5 bearish)
    all_scores  = [(t, v["score"], v["detail"]) for t, v in signals.items()]
    top_bullish = sorted(
        [(t, s, d) for t, s, d in all_scores if s >= 2],
        key=lambda x: x[1], reverse=True,
    )[:5]
    top_bearish = sorted(
        [(t, s, d) for t, s, d in all_scores if s <= -2],
        key=lambda x: x[1],
    )[:5]
    log("Sending daily summary email...")
    send_daily_summary(top_bullish, top_bearish, run_date)

    # 4. Signal flip detection (NEUTRAL -> BULLISH or BEARISH)
    prev_sigs    = load_previous_signals()
    is_first_run = len(prev_sigs) == 0
    if is_first_run:
        log("First run — saving signal baseline. Flip detection starts tomorrow.")
    else:
        flipped = []
        for ticker, info in signals.items():
            prev = prev_sigs.get(ticker, "NEUTRAL")
            curr = info["signal"]
            if prev == "NEUTRAL" and curr in ("BULLISH", "BEARISH"):
                flipped.append((ticker, prev, curr))
        if flipped:
            log("Signal flips detected: {}".format(", ".join(t for t, _, _ in flipped)))
            send_signal_flip_alerts(flipped, run_date)
        else:
            log("No signal flips today.")
    save_signals(signals)

    # 5. Price alerts (>5% single-day moves)
    big_movers = check_price_alerts()
    if big_movers:
        log("Price movers >5%: {}".format(", ".join(
            "{} ({:+.1f}%)".format(t, p) for t, p, _ in big_movers)))
        send_price_alerts(big_movers, run_date)
    else:
        log("No price moves >5% today.")

    # 6. Weekly backup (Sundays only)
    weekly_backup()

    # 7. Pipeline log CSV
    runtime = time.time() - start_time
    append_pipeline_log_csv(run_date, len(config.TICKERS), len(failed_steps), runtime)
    log("Total runtime: {:.1f}s".format(runtime))

    sys.exit(0 if all_ok else 1)
