# Central settings — edit this file to change which stocks you're tracking.

# Single stock used by legacy fetch scripts (do not remove)
TICKER       = "AAPL"
COMPANY_NAME = "Apple"

# All 50 core tracked tickers
TICKERS = [
    # Original research universe
    "AAPL", "NVDA", "TSLA", "GME", "AMC", "AMZN", "COIN", "MSFT", "SBUX", "SPCX",
    # Tech & Social
    "GOOGL", "META", "PLTR", "SNAP", "PINS", "RDDT", "SPOT", "NFLX", "DIS", "UBER",
    # Fintech & Finance
    "JPM", "GS", "HOOD", "PYPL", "SQ", "SOFI", "MSTR",
    # EV & Auto
    "RIVN", "LCID", "F", "GM",
    # Retail & Consumer
    "WMT", "TGT", "MCD", "CHWY", "NKE", "ABNB",
    # Defense & Space
    "RKLB", "LMT", "RTX", "BA",
    # Biotech & Pharma
    "PFE", "MRNA", "NVAX",
    # Quantum Computing
    "IONQ", "QBTS", "RGTI",
    # Energy
    "XOM", "CVX", "FSLR",
]

COMPANIES = {
    # Original universe
    "AAPL":  "Apple",
    "NVDA":  "Nvidia",
    "TSLA":  "Tesla",
    "GME":   "GameStop",
    "AMC":   "AMC Entertainment",
    "AMZN":  "Amazon",
    "COIN":  "Coinbase",
    "MSFT":  "Microsoft",
    "SBUX":  "Starbucks",
    "SPCX":  "Space Exploration ETF",
    # Tech & Social
    "GOOGL": "Alphabet (Google)",
    "META":  "Meta Platforms",
    "PLTR":  "Palantir",
    "SNAP":  "Snap",
    "PINS":  "Pinterest",
    "RDDT":  "Reddit",
    "SPOT":  "Spotify",
    "NFLX":  "Netflix",
    "DIS":   "Walt Disney",
    "UBER":  "Uber",
    # Fintech & Finance
    "JPM":   "JPMorgan Chase",
    "GS":    "Goldman Sachs",
    "HOOD":  "Robinhood",
    "PYPL":  "PayPal",
    "SQ":    "Block (Square)",
    "SOFI":  "SoFi Technologies",
    "MSTR":  "MicroStrategy",
    # EV & Auto
    "RIVN":  "Rivian",
    "LCID":  "Lucid Motors",
    "F":     "Ford",
    "GM":    "General Motors",
    # Retail & Consumer
    "WMT":   "Walmart",
    "TGT":   "Target",
    "MCD":   "McDonald's",
    "CHWY":  "Chewy",
    "NKE":   "Nike",
    "ABNB":  "Airbnb",
    # Defense & Space
    "RKLB":  "Rocket Lab",
    "LMT":   "Lockheed Martin",
    "RTX":   "RTX Corp",
    "BA":    "Boeing",
    # Biotech & Pharma
    "PFE":   "Pfizer",
    "MRNA":  "Moderna",
    "NVAX":  "Novavax",
    # Quantum Computing
    "IONQ":  "IonQ",
    "QBTS":  "D-Wave Quantum",
    "RGTI":  "Rigetti Computing",
    # Energy
    "XOM":   "ExxonMobil",
    "CVX":   "Chevron",
    "FSLR":  "First Solar",
}

# How many calendar days of history to pull each run
LOOKBACK_DAYS = 90

# Fixed tickers shown on the overview by default (pinned)
PINNED_TICKERS = ["AAPL", "NVDA", "TSLA", "MSFT"]
