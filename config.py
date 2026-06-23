# Central settings — edit this file to change which stocks you're tracking.

# Single stock used by fetch_price.py, fetch_stocktwits.py, fetch_trends.py
TICKER       = "AAPL"
COMPANY_NAME = "Apple"

# All 10 stocks tracked by fetch_news.py (and future multi-stock scripts)
TICKERS = ["AAPL", "NVDA", "TSLA", "GME", "AMC", "AMZN", "COIN", "MSFT", "SBUX", "SPCX"]

COMPANIES = {
    "AAPL":  "Apple",
    "NVDA":  "Nvidia",
    "TSLA":  "Tesla",
    "GME":   "GameStop",
    "AMC":   "AMC Entertainment",
    "AMZN":  "Amazon",
    "COIN":  "Coinbase",
    "MSFT":  "Microsoft",
    "SBUX":  "Starbucks",
    "SPCX":  "space exploration ETF",
}

# How many calendar days of history to pull each run
LOOKBACK_DAYS = 90
