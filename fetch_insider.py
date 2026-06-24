"""
fetch_insider.py
Pulls insider buying/selling data for all tracked tickers from the SEC EDGAR
API (Form 4 filings). No credentials required.
Saves: data/insider_TICKER.csv
Columns: filed_date, period_date, insider_name, title, transaction_code,
         transaction_type, shares, price_per_share, total_value
Transaction codes: P=Purchase, S=Sale, A=Award, M=Option exercise,
                   F=Tax withholding (auto-sell), G=Gift
"""

import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

import config

DATA_DIR  = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS   = {"User-Agent": "AltDataSignalTracker ellaktran@gmail.com"}
LOOKBACK  = config.LOOKBACK_DAYS

# Transaction code → human label
TX_LABELS = {
    "P": "Purchase", "S": "Sale", "A": "Award", "M": "Option exercise",
    "F": "Tax withholding (sale)", "G": "Gift", "D": "Return to issuer",
    "J": "Other acquisition", "K": "Other disposition", "L": "Small acquisition",
    "U": "Tender", "W": "Inherited", "X": "Exercise derivative",
}

_cik_cache: dict[str, str] = {}


def _get_cik(ticker: str):
    if ticker in _cik_cache:
        return _cik_cache[ticker]
    url = "https://www.sec.gov/files/company_tickers.json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            mapping = json.loads(r.read())
        for v in mapping.values():
            if v["ticker"].upper() == ticker.upper():
                cik = str(v["cik_str"]).zfill(10)
                _cik_cache[ticker] = cik
                return cik
    except Exception:
        pass
    return None


def _get(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()
    except Exception:
        return None


def _parse_form4(xml_bytes: bytes) -> list[dict]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    period    = (root.findtext("periodOfReport") or "").strip()
    name      = (root.findtext(".//rptOwnerName") or "").strip()
    title_val = (root.findtext(".//officerTitle") or
                 root.findtext(".//isDirector") or "").strip()
    if title_val in ("true", "1"):
        title_val = "Director"

    rows = []
    for tx in root.findall(".//nonDerivativeTransaction"):
        code  = (tx.findtext(".//transactionCode") or "").strip()
        shares_text = (tx.findtext(".//transactionShares/value") or "").strip()
        price_text  = (tx.findtext(".//transactionPricePerShare/value") or "").strip()
        try:
            shares = float(shares_text)
        except ValueError:
            shares = None
        try:
            price = float(price_text)
        except ValueError:
            price = None
        total = round(shares * price, 2) if shares and price else None
        rows.append({
            "period_date":      period,
            "insider_name":     name,
            "title":            title_val,
            "transaction_code": code,
            "transaction_type": TX_LABELS.get(code, code),
            "shares":           shares,
            "price_per_share":  price,
            "total_value":      total,
        })
    return rows


def fetch_insider_for_ticker(ticker: str, cik: str) -> bool:
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    raw = _get(url)
    if not raw:
        print(f"  {ticker}: could not reach EDGAR submissions")
        return False

    data = json.loads(raw)
    filings = data.get("filings", {}).get("recent", {})
    forms        = filings.get("form", [])
    filing_dates = filings.get("filingDate", [])
    accessions   = filings.get("accessionNumber", [])
    issuer_cik   = data.get("cik", "")  # short CIK for archive URL

    cutoff = str(date.today() - timedelta(days=LOOKBACK))
    rows = []

    for i, form in enumerate(forms):
        if form != "4":
            continue
        if filing_dates[i] < cutoff:
            break   # submissions are sorted newest-first; stop at cutoff
        acc_clean = accessions[i].replace("-", "")
        xml_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(issuer_cik)}"
            f"/{acc_clean}/{accessions[i]}-index.htm"
        )
        # Find the form4.xml file
        idx_raw = _get(xml_url)
        if not idx_raw:
            continue
        idx_html = idx_raw.decode("utf-8", errors="replace")
        xml_links = re.findall(r'href="([^"]+form4[^"]*\.xml)"', idx_html, re.I)
        if not xml_links:
            xml_links = re.findall(r'href="([^"]+\.xml)"', idx_html)
        if not xml_links:
            continue
        # Prefer the non-stylesheet XML
        for lnk in xml_links:
            if "xsl" not in lnk.lower():
                xml_url2 = "https://www.sec.gov" + lnk
                break
        else:
            xml_url2 = "https://www.sec.gov" + xml_links[-1]

        xml_raw = _get(xml_url2)
        if not xml_raw:
            continue
        parsed = _parse_form4(xml_raw)
        for r in parsed:
            r["filed_date"] = filing_dates[i]
            rows.append(r)
        time.sleep(0.15)   # EDGAR rate limit: ≤10 req/s

    if not rows:
        print(f"  {ticker}: no Form 4 transactions in last {LOOKBACK} days")
        return False

    df = pd.DataFrame(rows)[[
        "filed_date", "period_date", "insider_name", "title",
        "transaction_code", "transaction_type", "shares",
        "price_per_share", "total_value",
    ]]
    df = df.sort_values("period_date", ascending=False)

    out = DATA_DIR / f"insider_{ticker}.csv"
    # Always overwrite — we re-pull full LOOKBACK window each run
    df.to_csv(out, index=False)

    buys  = (df["transaction_code"] == "P").sum()
    sells = (df["transaction_code"] == "S").sum()
    print(f"  {ticker}: {len(df)} transactions  (P={buys} buys, S={sells} sells)")
    return True


def fetch_insider():
    print(f"Fetching insider data (SEC Form 4) for {len(config.TICKERS)} tickers...\n")
    # Load CIK map once
    url = "https://www.sec.gov/files/company_tickers.json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            ticker_map = {v["ticker"].upper(): str(v["cik_str"]).zfill(10)
                          for v in json.loads(r.read()).values()}
    except Exception as e:
        print(f"Failed to load CIK map: {e}")
        return

    ok = fail = 0
    for ticker in config.TICKERS:
        cik = ticker_map.get(ticker.upper())
        if not cik:
            print(f"  {ticker}: no CIK found — skipping")
            fail += 1
            continue
        if fetch_insider_for_ticker(ticker, cik):
            ok += 1
        else:
            fail += 1
        time.sleep(0.3)

    print(f"\n--- Insider summary: {ok} OK, {fail} failed/skipped ---")


if __name__ == "__main__":
    fetch_insider()
