"""
run_pipeline.py
Runs all data fetchers in sequence, logs results, then pushes fresh
CSV files to GitHub so the live Streamlit dashboard updates automatically.
Usage: python3 run_pipeline.py
"""

import subprocess
import sys
import traceback
from datetime import datetime, date
from pathlib import Path

import config

PROJECT_DIR = Path(__file__).parent
LOG_PATH    = PROJECT_DIR / "data" / "pipeline_log.txt"
TOKEN_FILE  = PROJECT_DIR / ".github_token"
GITHUB_REPO = "https://github.com/ellaktran-hub/alt-data-signal-tracker.git"


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
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
        # Stage only the data directory
        subprocess.run(
            ["git", "add", "data/"],
            cwd=str(PROJECT_DIR), check=True, capture_output=True,
        )

        # Check if there's actually anything new to commit
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(PROJECT_DIR),
        )
        if diff.returncode == 0:
            log("GitHub push skipped — no changes in data/ since last push.")
            return True

        # Commit with today's date
        subprocess.run(
            ["git", "commit", "-m", f"data: pipeline update {date.today()}"],
            cwd=str(PROJECT_DIR), check=True, capture_output=True,
        )

        # Push — capture_output hides the token from appearing in any logs
        push_url = f"https://{token}@github.com/ellaktran-hub/alt-data-signal-tracker.git"
        result = subprocess.run(
            ["git", "push", push_url, "main"],
            cwd=str(PROJECT_DIR), capture_output=True, text=True,
        )
        if result.returncode == 0:
            log("GitHub push successful — live dashboard will update within ~60 seconds.")
            return True
        else:
            # Sanitize error output so token isn't logged
            err = result.stderr.replace(token, "***")
            log(f"GitHub push failed: {err.strip()}")
            return False

    except subprocess.CalledProcessError as e:
        log(f"GitHub push failed: {e}")
        return False


if __name__ == "__main__":
    log(f"========== Pipeline run started | tickers: {', '.join(config.TICKERS)} ==========")

    steps = [
        ("Stock prices (Yahoo Finance)",    "fetch_price",       "fetch_price"),
        ("Sentiment (StockTwits)",          "fetch_stocktwits",  "fetch_stocktwits"),
        ("Search interest (Google Trends)", "fetch_trends",      "fetch_trends"),
        ("News headlines (Yahoo Finance)",  "fetch_news",        "fetch_news"),
        ("Wikipedia page views",            "fetch_wikipedia",   "fetch_wikipedia"),
        ("Lead/lag correlations",           "correlations",      "compute_correlations"),
    ]

    results = {}
    for label, module, fn in steps:
        log(f"Starting: {label}")
        try:
            mod = __import__(module)
            getattr(mod, fn)()
            log(f"OK: {label}")
            results[label] = "OK"
        except Exception:
            log(f"FAILED: {label}")
            log(traceback.format_exc())
            results[label] = "FAILED"

    log("========== Pipeline summary ==========")
    all_ok = True
    for label, status in results.items():
        log(f"  {status:6s}  {label}")
        if status != "OK":
            all_ok = False

    log("Pipeline finished." if all_ok else "Pipeline finished with errors — check log above.")

    # Push fresh data to GitHub regardless of partial failures —
    # even if one fetcher failed, the others produced valid updated CSVs
    log("========== GitHub push ==========")
    git_push()

    sys.exit(0 if all_ok else 1)
