"""
run_pipeline.py
Runs all data fetchers in sequence and logs the results.
This is the only script you need to run to update all your data.
Usage: python3 run_pipeline.py
"""

import sys
import traceback
from datetime import datetime
from pathlib import Path

import config

LOG_PATH = Path(__file__).parent / "data" / "pipeline_log.txt"


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def run_step(label, module_name):
    log(f"--- {label} ---")
    try:
        module = __import__(module_name)
        # Each fetch module exposes a single function named after itself
        fn_name = module_name.replace("fetch_", "fetch_")
        getattr(module, fn_name)()
        log(f"{label}: OK")
        return True
    except Exception:
        log(f"{label}: FAILED")
        log(traceback.format_exc())
        return False


if __name__ == "__main__":
    log(f"========== Pipeline run started | tickers: {', '.join(config.TICKERS)} ==========")

    steps = [
        ("Stock prices (Yahoo Finance)",    "fetch_price",       "fetch_price"),
        ("Sentiment (StockTwits)",          "fetch_stocktwits",  "fetch_stocktwits"),
        ("Search interest (Google Trends)", "fetch_trends",      "fetch_trends"),
        ("News headlines (Yahoo Finance)",  "fetch_news",        "fetch_news"),
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
    sys.exit(0 if all_ok else 1)
