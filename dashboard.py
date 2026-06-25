"""
dashboard.py
Professional financial research dashboard — Alt Data Signal Tracker.
Run with: python3 -m streamlit run dashboard.py
"""

import json
import math
import sys
from pathlib import Path
from datetime import date, datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

try:
    import yfinance as yf
    _YF_OK = True
except ImportError:
    _YF_OK = False

sys.path.insert(0, str(Path(__file__).parent))
import config

DATA_DIR      = Path(__file__).parent / "data"
WATCHLIST_FILE = Path(__file__).parent / "watchlist.json"


def load_watchlist():
    """Load starred tickers from JSON file."""
    if WATCHLIST_FILE.exists():
        try:
            data = json.loads(WATCHLIST_FILE.read_text())
            return set(data) if isinstance(data, list) else set()
        except Exception:
            return set()
    return set()


def save_watchlist(wl):
    """Persist watchlist to JSON file."""
    WATCHLIST_FILE.write_text(json.dumps(sorted(wl), indent=2))

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Alt Data Signal Tracker",
    page_icon="▲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design tokens ──────────────────────────────────────────────────────────────
BG          = "#FAF6EF"
SURFACE     = "#F2EBE0"
SURFACE2    = "#E8DDD0"
BORDER      = "#C8B89A"
TEXT        = "#2C2416"
MUTED       = "#7A6A52"
ACCENT      = "#8B6F47"
DARK_HEADER = "#1C160E"
C1 = "#6B4226"
C2 = "#C47D3E"
C3 = "#2C2416"
C4 = "#A0896B"
C5 = "#5B7FA6"   # slate-blue — Wikipedia trace
GREEN = "#3A6B35"
RED   = "#9B3A28"

# ── Styles ─────────────────────────────────────────────────────────────────────
st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1'
    '&family=Inter:wght@300;400;500;600;700'
    '&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">',
    unsafe_allow_html=True,
)
_css = Path(__file__).parent / "styles" / "style.css"
with open(_css) as _f:
    st.markdown(f"<style>{_f.read()}</style>", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
if "basket" not in st.session_state:
    st.session_state["basket"] = list(config.PINNED_TICKERS)
if "basket_view" not in st.session_state:
    st.session_state["basket_view"] = False
if "watchlist" not in st.session_state:
    st.session_state["watchlist"] = load_watchlist()
if "sector_filter" not in st.session_state:
    st.session_state["sector_filter"] = "All"


# ── ET timezone helper ─────────────────────────────────────────────────────────
def now_et():
    return datetime.now(ZoneInfo("America/New_York"))

def format_et(dt):
    hour = dt.hour % 12 or 12
    minute = dt.strftime("%M")
    ampm   = "AM" if dt.hour < 12 else "PM"
    return f"{dt.strftime('%b')} {dt.day}, {dt.year} · {hour}:{minute} {ampm} ET"

def format_et_short(dt):
    hour   = dt.hour % 12 or 12
    minute = dt.strftime("%M")
    ampm   = "AM" if dt.hour < 12 else "PM"
    return f"{dt.strftime('%b')} {dt.day} · {hour}:{minute} {ampm}"


def get_last_updated():
    """Return most-recent mtime of any price CSV, as an ET datetime."""
    files = list(DATA_DIR.glob("prices_*.csv"))
    if not files:
        return None
    try:
        mtime = max(f.stat().st_mtime for f in files)
        return datetime.fromtimestamp(mtime, tz=ZoneInfo("America/New_York"))
    except Exception:
        return None


# ── Plotly layout factory ──────────────────────────────────────────────────────
def chart_layout(title="", height=270):
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=MUTED, family="Inter", size=11),
        title=dict(
            text=title,
            font=dict(size=10, color=MUTED, family="Inter"),
            x=0, xanchor="left", y=0.97,
        ),
        xaxis=dict(
            gridcolor="rgba(200,184,154,0.25)", linecolor=BORDER,
            tickfont=dict(size=9, color=MUTED, family="JetBrains Mono"),
            showgrid=True, zeroline=False,
        ),
        yaxis=dict(
            gridcolor="rgba(200,184,154,0.25)", linecolor=BORDER,
            tickfont=dict(size=9, color=MUTED, family="JetBrains Mono"),
            showgrid=True, zeroline=False,
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)",
            font=dict(size=9, color=MUTED, family="Inter"),
            orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
        ),
        margin=dict(l=52, r=16, t=36, b=36),
        height=height,
        hovermode="x unified",
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=BORDER,
                        font=dict(family="JetBrains Mono", size=11, color=TEXT)),
    )


# ── Data loaders (unchanged) ───────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_prices(ticker):
    p = DATA_DIR / f"prices_{ticker}.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, index_col="date", parse_dates=True)
    df.index = pd.to_datetime(df.index)
    return df

@st.cache_data(ttl=300)
def load_stocktwits(ticker):
    p = DATA_DIR / f"stocktwits_{ticker}.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, index_col="date", parse_dates=True)
    df.index = pd.to_datetime(df.index)
    return df.dropna(how="all")

@st.cache_data(ttl=300)
def load_trends(ticker):
    p = DATA_DIR / f"trends_{ticker}.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, index_col="date", parse_dates=True)
    df.index = pd.to_datetime(df.index)
    if df.empty:
        return df
    best = df.mean().idxmax()
    return df[[best]].rename(columns={best: "interest"})

@st.cache_data(ttl=300)
def load_news(ticker):
    p = DATA_DIR / f"news_{ticker}.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, index_col="date", parse_dates=True)
    df.index = pd.to_datetime(df.index)
    return df

@st.cache_data(ttl=300)
def load_wikipedia(ticker):
    p = DATA_DIR / f"wikipedia_{ticker}.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, index_col="date", parse_dates=True)
    df.index = pd.to_datetime(df.index)
    return df


# ── Signal helpers (unchanged) ─────────────────────────────────────────────────
def safe_last(df, col):
    if df.empty or col not in df.columns:
        return None
    vals = df[col].dropna()
    return float(vals.iloc[-1]) if len(vals) > 0 else None

def compute_signal(bullish_pct, trends_score, trends_avg, news_sent, price_chg):
    votes = []
    if bullish_pct is not None:
        votes.append(1 if bullish_pct > 55 else (-1 if bullish_pct < 40 else 0))
    if news_sent is not None:
        votes.append(1 if news_sent > 0.1 else (-1 if news_sent < -0.1 else 0))
    if trends_score is not None and trends_avg is not None:
        votes.append(1 if trends_score > trends_avg * 1.1 else (-1 if trends_score < trends_avg * 0.9 else 0))
    if price_chg is not None:
        votes.append(1 if price_chg > 0.5 else (-1 if price_chg < -0.5 else 0))
    if not votes:
        return "NEUTRAL"
    s = sum(votes)
    return "BULLISH" if s >= 2 else ("BEARISH" if s <= -2 else "NEUTRAL")

def norm_0_100(series):
    s = series.dropna()
    if len(s) < 2:
        return s
    mn, mx = s.min(), s.max()
    return pd.Series(50.0, index=s.index) if mx == mn else (s - mn) / (mx - mn) * 100

def _price_norm(ticker):
    df = load_prices(ticker)
    if df.empty:
        return None
    p = df["close_price"].dropna()
    return norm_0_100(p) if len(p) >= 2 else None

def note(text):
    st.markdown(f'<div class="chart-note">{text}</div>', unsafe_allow_html=True)

def tab_intro(text):
    st.markdown(f'<div class="tab-desc">{text}</div>', unsafe_allow_html=True)

def sparse_note():
    st.markdown(
        '<div class="sparse-note">⚠ Fewer than 3 days collected. '
        'This chart fills in as the daily pipeline runs each morning. '
        'Signals become meaningful after ~30 days of accumulation.</div>',
        unsafe_allow_html=True,
    )

_NORM_SUBTITLE = (
    "<br><sup style='font-style:italic;font-size:9px;color:#7A6A52'>"
    "Price shown as amber line, normalized to same 0–100 scale for comparison</sup>"
)


# ── yfinance helpers ───────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def validate_ticker_yf(symbol):
    if not _YF_OK:
        return True, symbol
    try:
        info = yf.Ticker(symbol).info
        name = info.get("shortName") or info.get("longName")
        return bool(name), (name or symbol)
    except Exception:
        return False, None

@st.cache_data(ttl=300)
def fetch_live_quote(symbol):
    if not _YF_OK:
        return None, None
    try:
        hist = yf.Ticker(symbol).history(period="2d")
        if hist.empty:
            return None, None
        price = float(hist["Close"].iloc[-1])
        chg   = None
        if len(hist) >= 2:
            prev = float(hist["Close"].iloc[-2])
            chg  = (price - prev) / prev * 100 if prev else None
        return price, chg
    except Exception:
        return None, None

@st.cache_data(ttl=3600)
def fetch_yf_history(symbol):
    if not _YF_OK:
        return pd.DataFrame()
    try:
        hist = yf.Ticker(symbol).history(period="90d")
        if hist.empty:
            return pd.DataFrame()
        hist.index = hist.index.tz_localize(None)
        return hist[["Close"]].rename(columns={"Close": "close_price"})
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_recent_headlines(ticker, n=6):
    if not _YF_OK:
        return []
    try:
        items = yf.Ticker(ticker).news or []
    except Exception:
        return []
    headlines = []
    for item in items[:30]:
        content = item.get("content", item)
        title   = (content.get("title") or "").strip()
        if not title:
            continue
        pub_str  = content.get("pubDate") or content.get("displayTime", "")
        pub_date = None
        try:
            pub_date = datetime.strptime(pub_str, "%Y-%m-%dT%H:%M:%SZ").date()
        except (ValueError, TypeError):
            try:
                pub_date = datetime.utcfromtimestamp(int(content.get("providerPublishTime", 0))).date()
            except Exception:
                pass
        canonical = content.get("canonicalUrl") or {}
        url = canonical.get("url", "") if isinstance(canonical, dict) else ""
        if not url:
            url = content.get("link", content.get("url", ""))
        provider = content.get("provider") or {}
        source   = provider.get("displayName", "") if isinstance(provider, dict) else ""
        headlines.append({"title": title, "date": pub_date, "url": url, "source": source})
        if len(headlines) >= n:
            break
    return headlines


# ── Summary data ───────────────────────────────────────────────────────────────
def build_summary():
    rows = []
    for ticker in config.TICKERS:
        price_df  = load_prices(ticker)
        st_df     = load_stocktwits(ticker)
        trends_df = load_trends(ticker)
        news_df   = load_news(ticker)

        price = safe_last(price_df, "close_price")
        price_chg = None
        if not price_df.empty and len(price_df["close_price"].dropna()) >= 2:
            s = price_df["close_price"].dropna()
            price_chg = (s.iloc[-1] - s.iloc[-2]) / s.iloc[-2] * 100

        bullish_pct = None
        if not st_df.empty and {"bullish_count", "message_count"}.issubset(st_df.columns):
            valid = st_df.dropna(subset=["message_count"])
            if len(valid) > 0:
                last = valid.iloc[-1]
                if last["message_count"] > 0:
                    bullish_pct = last["bullish_count"] / last["message_count"] * 100

        trends_score = safe_last(trends_df, "interest")
        trends_avg   = float(trends_df["interest"].mean()) if not trends_df.empty else None
        news_sent    = safe_last(news_df, "avg_sentiment")
        signal       = compute_signal(bullish_pct, trends_score, trends_avg, news_sent, price_chg)

        if price_chg is not None:
            if price_chg > 0.001:
                chg_str, chg_color = f"▲ {price_chg:.2f}%", GREEN
            elif price_chg < -0.001:
                chg_str, chg_color = f"▼ {abs(price_chg):.2f}%", RED
            else:
                chg_str, chg_color = f"{price_chg:.2f}%", MUTED
        else:
            chg_str, chg_color = "—", MUTED

        sig_color = GREEN if signal == "BULLISH" else (RED if signal == "BEARISH" else MUTED)

        rows.append({
            "ticker":        ticker,
            "company":       config.COMPANIES.get(ticker, ticker),
            "price":         f"${price:,.2f}" if price is not None else "—",
            "chg":           chg_str,
            "chg_color":     chg_color,
            "chg_raw":       price_chg,
            "bullish_pct":   f"{bullish_pct:.0f}%" if bullish_pct is not None else "—",
            "trends":        f"{trends_score:.0f}/100" if trends_score is not None else "—",
            "news_sent":     f"{int(round(news_sent*100)):+d}" if news_sent is not None else "—",
            "news_sent_raw": news_sent,
            "signal":        signal,
            "sig_color":     sig_color,
        })
    return rows


# ── Sidebar ────────────────────────────────────────────────────────────────────
def show_sidebar(rows_by_ticker):
    with st.sidebar:
        st.markdown('<div class="sb-title">My Basket</div>', unsafe_allow_html=True)

        basket = st.session_state.get("basket", list(config.PINNED_TICKERS))

        for ticker in list(basket):
            r         = rows_by_ticker.get(ticker, {})
            price_str = r.get("price", "—")
            chg_str   = r.get("chg", "—")
            chg_color = r.get("chg_color", MUTED)
            sig_str   = r.get("signal", "—")
            sig_color = r.get("sig_color", MUTED)

            col_item, col_rm = st.columns([5, 1])
            with col_item:
                st.markdown(
                    f'<div class="sb-item">'
                    f'<div class="sb-item-top">'
                    f'<span class="sb-ticker">{ticker}</span>'
                    f'<span class="sb-sig" style="color:{sig_color}">{sig_str}</span>'
                    f'</div>'
                    f'<div class="sb-item-price">'
                    f'<span class="sb-price">{price_str}</span>'
                    f'<span class="sb-chg" style="color:{chg_color}">{chg_str}</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with col_rm:
                if st.button("×", key=f"rm_{ticker}", help=f"Remove {ticker}"):
                    st.session_state["basket"].remove(ticker)
                    st.rerun()

        st.markdown("")
        st.markdown('<div class="sb-add-label">Add ticker</div>', unsafe_allow_html=True)
        available = [t for t in config.TICKERS if t not in basket]
        selected_sym = st.selectbox(
            "Add ticker",
            options=available,
            index=None,
            placeholder="Search ticker…",
            label_visibility="collapsed",
            key="basket_add_select",
        )
        if st.button("ADD TO BASKET", key="basket_add_btn", use_container_width=True):
            sym = selected_sym or ""
            if sym and sym not in st.session_state["basket"]:
                st.session_state["basket"].append(sym)
                st.rerun()
        st.markdown("")
        basket_view = st.session_state.get("basket_view", False)
        if basket_view:
            if st.button("VIEW ALL TICKERS", key="view_all_btn", use_container_width=True):
                st.session_state["basket_view"] = False
                st.rerun()
        else:
            if st.button("SEE MY BASKET", key="see_basket_btn", use_container_width=True):
                st.session_state["basket_view"] = True
                st.rerun()

        st.markdown(
            '<div class="sb-about-btn">'
            '<a href="?page=predictions">Price Predictions</a>'
            '</div>'
            '<div class="sb-about-btn">'
            '<a href="?page=about">About this project</a>'
            '</div>',
            unsafe_allow_html=True,
        )


# ── Ticker strip ───────────────────────────────────────────────────────────────
def build_ticker_strip_html(rows):
    top5 = sorted(
        rows,
        key=lambda r: abs(r["chg_raw"]) if r["chg_raw"] is not None else 0,
        reverse=True,
    )[:5]

    def item_html(r):
        return (
            f'<span class="strip-item">'
            f'<span class="strip-ticker">{r["ticker"]}</span>'
            f'<span class="strip-sig" style="color:{r["sig_color"]}">{r["signal"]}</span>'
            f'<span class="strip-chg" style="color:{r["chg_color"]}">{r["chg"]}</span>'
            f'</span>'
            f'<span class="strip-sep" aria-hidden="true">|</span>'
        )

    items = "".join(item_html(r) for r in top5)
    return (
        f'<div class="ticker-strip-outer" aria-label="Top movers ticker strip">'
        f'<div class="strip-track">{items * 3}</div>'
        f'</div>'
    )


# ── Market summary chips ───────────────────────────────────────────────────────
def build_market_chips_html(rows):
    total   = len(rows)
    bullish = sum(1 for r in rows if r["signal"] == "BULLISH")
    bearish = sum(1 for r in rows if r["signal"] == "BEARISH")
    neutral = total - bullish - bearish

    news_vals    = [r["news_sent_raw"] for r in rows if r["news_sent_raw"] is not None]
    avg_news_raw = sum(news_vals) / len(news_vals) if news_vals else 0.0
    avg_news_int = int(round(avg_news_raw * 100))
    avg_sign     = "+" if avg_news_int >= 0 else ""

    ts       = format_et(now_et())
    ts_short = format_et_short(now_et())

    _sig_tip  = ("Count of tickers right now with a BULLISH, BEARISH, or NEUTRAL composite signal "
                 "— built from a majority vote across StockTwits, News Sentiment, Google Trends, and Price Change.")
    _news_tip = ("Average VADER sentiment score across all tracked tickers, scaled −100 to +100. "
                 "Positive = net-bullish news today. Zero = neutral. "
                 "Computed from Yahoo Finance headlines each morning.")

    return f"""
<div class="market-chips">
  <div class="chip">
    <div class="chip-label">Tickers Tracked</div>
    <div class="chip-value" data-countup-int="{total}">{total}</div>
  </div>
  <div class="chip">
    <div class="chip-label">Signal Distribution <span class="chip-tip"><button class="chip-info-btn" aria-label="About Signal Distribution">ⓘ</button><div class="chip-info-popup">{_sig_tip}</div></span></div>
    <div class="chip-dist">
      <span class="dist-item"><span class="dist-b" data-countup-int="{bullish}">{bullish}</span> Bullish</span>
      <span class="dist-dot">·</span>
      <span class="dist-item"><span class="dist-r" data-countup-int="{bearish}">{bearish}</span> Bearish</span>
      <span class="dist-dot">·</span>
      <span class="dist-item"><span class="dist-n" data-countup-int="{neutral}">{neutral}</span> Neutral</span>
    </div>
  </div>
  <div class="chip">
    <div class="chip-label">Avg News Sentiment <span class="chip-tip"><button class="chip-info-btn" aria-label="About Avg News Sentiment">ⓘ</button><div class="chip-info-popup">{_news_tip}</div></span></div>
    <div class="chip-value" data-countup-int="{abs(avg_news_int)}" data-countup-prefix="{avg_sign}">
      {avg_sign}{abs(avg_news_int)}
    </div>
  </div>
  <div class="chip">
    <div class="chip-label">Last Updated</div>
    <div class="chip-value">
      <span class="live-pulse" aria-label="Live data"></span>
      <span class="chip-time chip-time-full">{ts}</span>
      <span class="chip-time chip-time-short" aria-hidden="true">{ts_short}</span>
    </div>
  </div>
</div>
"""


# ── Signal distribution chart ──────────────────────────────────────────────────
def build_signal_dist_chart(rows):
    bullish = sum(1 for r in rows if r["signal"] == "BULLISH")
    bearish = sum(1 for r in rows if r["signal"] == "BEARISH")
    neutral = len(rows) - bullish - bearish
    total   = len(rows)

    fig = go.Figure()
    if bullish:
        fig.add_trace(go.Bar(x=[bullish], y=["dist"], orientation="h",
                             marker_color=GREEN, name="Bullish",
                             hovertemplate=f"{bullish} BULLISH<extra></extra>"))
    if neutral:
        fig.add_trace(go.Bar(x=[neutral], y=["dist"], orientation="h",
                             marker_color=C4, name="Neutral",
                             hovertemplate=f"{neutral} NEUTRAL<extra></extra>"))
    if bearish:
        fig.add_trace(go.Bar(x=[bearish], y=["dist"], orientation="h",
                             marker_color=RED, name="Bearish",
                             hovertemplate=f"{bearish} BEARISH<extra></extra>"))

    layout = chart_layout("SIGNAL DISTRIBUTION — ALL TICKERS", height=78)
    layout["barmode"]   = "stack"
    layout["margin"]    = dict(l=10, r=10, t=28, b=4)
    layout["xaxis"]["range"]          = [0, total]
    layout["xaxis"]["showgrid"]       = False
    layout["xaxis"]["showticklabels"] = False
    layout["yaxis"]["showticklabels"] = False
    layout["yaxis"]["showgrid"]       = False
    layout["legend"]["y"]             = 1.3
    fig.update_layout(**layout)
    return fig


# ── Glossary / metric definitions ──────────────────────────────────────────────
_GLOSSARY = [
    ("price chg %",
     "the percentage change in closing price over the past trading day. "
     "positive means the stock gained, negative means it declined."),
    ("bullish %",
     "the share of alt data signals currently pointing bullish for this ticker. "
     "a high reading means most data sources agree the outlook is positive — "
     "but check trends and news sentiment to confirm."),
    ("trends",
     "google search interest for this ticker, scored 0–100. 100 is the peak interest "
     "over the measured period. rising scores can signal growing retail attention "
     "before it shows up in price."),
    ("news sent",
     "aggregate news sentiment scored from −100 (fully bearish coverage) to +100 (fully bullish). "
     "scores near zero mean mixed or neutral reporting. "
     "works best as a confirming signal alongside bullish %."),
    ("signal",
     "the composite signal combining all alt data sources. bullish means the majority of sources "
     "align positive; bearish means majority negative; neutral means mixed or insufficient data "
     "to call a direction. use it as a weight of evidence, not a guarantee."),
]

def show_glossary():
    with st.expander("METRIC DEFINITIONS", expanded=False):
        entries_html = "".join(
            f'<div class="glossary-entry">'
            f'<div class="glossary-term">{term}</div>'
            f'<div class="glossary-def">{defn}</div>'
            f'</div>'
            for term, defn in _GLOSSARY
        )
        st.markdown(
            f'<div class="glossary-grid">{entries_html}</div>',
            unsafe_allow_html=True,
        )


# ── Signal table HTML ──────────────────────────────────────────────────────────
_TOOLTIPS = {
    "CHG %": (
        "the percentage change in closing price over the past trading day. "
        "positive means the stock gained, negative means it declined."
    ),
    "BULLISH %": (
        "the share of alt data signals currently pointing bullish for this ticker. "
        "a high reading means most data sources agree the outlook is positive — "
        "but check trends and news sentiment to confirm."
    ),
    "TRENDS": (
        "google search interest for this ticker, scored 0–100. 100 is the peak interest "
        "over the measured period. rising scores can signal growing retail attention "
        "before it shows up in price."
    ),
    "NEWS SENT": (
        "aggregate news sentiment scored from −100 (fully bearish coverage) to +100 (fully bullish). "
        "scores near zero mean mixed or neutral reporting. "
        "works best as a confirming signal alongside bullish %."
    ),
    "SIGNAL": (
        "the composite signal combining all alt data sources. bullish means the majority of sources "
        "align positive; bearish means majority negative; neutral means mixed or insufficient data "
        "to call a direction. use it as a weight of evidence, not a guarantee."
    ),
}

def _th(label, width, center=False):
    cls = "data-tbl-th ctr" if center else "data-tbl-th"
    if label in _TOOLTIPS:
        return (
            f'<th class="{cls}">{label}'
            f'<span class="th-tip" tabindex="0">'
            f'<span class="th-tip-icon" aria-label="Definition for {label}">ⓘ</span>'
            f'<span class="th-tip-box" role="tooltip">{_TOOLTIPS[label]}</span>'
            f'</span></th>'
        )
    return f'<th class="{cls}">{label}</th>'

# Sortable columns: (label, min-width, centered, sortable, data-type)
_COLS = [
    ("★",         "34px",  True,  False, "str"),   # watchlist star — not sortable
    ("TICKER",    "68px",  False, True,  "str"),
    ("COMPANY",   None,    False, True,  "str"),
    ("PRICE",     "80px",  True,  True,  "num"),
    ("CHG %",     "90px",  True,  True,  "num"),
    ("BULLISH %", "80px",  True,  True,  "num"),
    ("TRENDS",    "75px",  True,  True,  "num"),
    ("NEWS SENT", "90px",  True,  True,  "num"),
    ("SIGNAL",    "90px",  True,  True,  "num"),
    ("30D TREND", "90px",  True,  False, "str"),   # sparkline — not sortable
    ("",          "68px",  True,  False, "str"),   # VIEW button
]


def build_table_html(rows, watchlist=None):
    watchlist = watchlist or set()

    def _th_cell(label, min_w, ctr, sortable, dtype):
        style = f'style="min-width:{min_w}"' if min_w else ""
        base  = "data-tbl-th ctr" if ctr else "data-tbl-th"
        cls   = (base + " sortable") if sortable else base
        sort_attr = f'data-dtype="{dtype}"' if sortable else ""
        if label in _TOOLTIPS:
            inner = (
                f'{label}'
                f'<span class="th-tip" tabindex="0">'
                f'<span class="th-tip-icon" aria-label="Definition for {label}">ⓘ</span>'
                f'<span class="th-tip-box" role="tooltip">{_TOOLTIPS[label]}</span>'
                f'</span>'
            )
        else:
            inner = label
        icon = '<span class="sort-icon">⇅</span>' if sortable else ""
        return f'<th class="{cls}" {style} {sort_attr}>{inner}{icon}</th>'

    head_cells = "".join(
        _th_cell(label, min_w, ctr, sortable, dtype)
        for label, min_w, ctr, sortable, dtype in _COLS
    )
    head = f'<thead><tr id="tbl-header-row">{head_cells}</tr></thead>'

    body = "<tbody>"
    for i, r in enumerate(rows):
        ticker      = r["ticker"]
        is_starred  = ticker in watchlist
        row_extra   = " watchlisted" if is_starred else ""
        row_cls     = ("even" if i % 2 == 0 else "odd") + row_extra
        delay_ms    = 800 + i * 80

        # Raw numeric values for sort (stored in data-sort)
        price_raw   = float(r["price"].replace("$", "").replace(",", "")) if r["price"] != "—" else -999999
        chg_raw     = r.get("chg_raw") or 0.0
        bull_raw    = float(r["bullish_pct"].replace("%", "")) if r["bullish_pct"] != "—" else -1
        trends_raw  = float(r["trends"].split("/")[0]) if r["trends"] != "—" else -1
        news_raw    = float(r["news_sent"].replace("+", "")) if r["news_sent"] != "—" else -999
        sig_num     = {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1}.get(r["signal"], 0)

        star_cls  = "star-btn starred" if is_starred else "star-btn"
        star_icon = "★" if is_starred else "☆"
        star_title = "Unstar" if is_starred else "Star"

        sparkline = build_table_sparkline(ticker, r["sig_color"])

        body += (
            f'<tr class="{row_cls}" style="animation-delay:{delay_ms}ms">'
            f'<td class="data-tbl-td" style="text-align:center">'
            f'<span class="{star_cls}" data-star="{ticker}" title="{star_title} {ticker}" role="button">{star_icon}</span>'
            f'</td>'
            f'<td class="data-tbl-td tkr" data-sort="{ticker}">{ticker}</td>'
            f'<td class="data-tbl-td left" data-sort="{r["company"]}">{r["company"]}</td>'
            f'<td class="data-tbl-td num" data-sort="{price_raw}">{r["price"]}</td>'
            f'<td class="data-tbl-td num" data-sort="{chg_raw}" style="color:{r["chg_color"]}">{r["chg"]}</td>'
            f'<td class="data-tbl-td num" data-sort="{bull_raw}">{r["bullish_pct"]}</td>'
            f'<td class="data-tbl-td num" data-sort="{trends_raw}">{r["trends"]}</td>'
            f'<td class="data-tbl-td num" data-sort="{news_raw}">{r["news_sent"]}</td>'
            f'<td class="data-tbl-td num" data-sort="{sig_num}" style="color:{r["sig_color"]};font-weight:600">{r["signal"]}</td>'
            f'<td class="data-tbl-td" style="text-align:center">{sparkline}</td>'
            f'<td class="data-tbl-td num"><a href="?ticker={ticker}" class="tbl-detail-btn">VIEW →</a></td>'
            f'</tr>'
        )
    body += "</tbody>"

    return (
        f'<div class="data-tbl-wrap">'
        f'<table class="data-tbl" id="signal-tbl">{head}{body}</table>'
        f'</div>'
    )


# ── Count-up + Sort + Fullscreen JS ───────────────────────────────────────────
def build_animations_js():
    return """
<script>
(function () {
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Count-up animations ─────────────────────────────────────── */
  if (!reduced) {
    function easeOut(t) { return 1 - (1 - t) * (1 - t); }
    function animateInt(el, target) {
      var start = performance.now(), dur = 600;
      (function step(ts) {
        var p = Math.min((ts - start) / dur, 1);
        el.textContent = Math.round(easeOut(p) * target);
        if (p < 1) requestAnimationFrame(step);
        else el.textContent = target;
      })(start);
    }
    function animateFloat(el, target, dec, prefix) {
      var start = performance.now(), dur = 600;
      prefix = prefix || '';
      (function step(ts) {
        var p = Math.min((ts - start) / dur, 1);
        el.textContent = prefix + (easeOut(p) * target).toFixed(dec);
        if (p < 1) requestAnimationFrame(step);
        else el.textContent = prefix + target.toFixed(dec);
      })(start);
    }
    setTimeout(function () {
      document.querySelectorAll('[data-countup-int]').forEach(function (el) {
        animateInt(el, parseInt(el.dataset.countupInt, 10));
      });
      document.querySelectorAll('[data-countup-float]').forEach(function (el) {
        animateFloat(el,
          parseFloat(el.dataset.countupFloat),
          parseInt(el.dataset.countupDec || '2', 10),
          el.dataset.countupPrefix || '');
      });
    }, 400);
  }

  /* ── Client-side table sort ──────────────────────────────────── */
  function initTableSort() {
    var pd  = window.parent.document;
    var tbl = pd.getElementById('signal-tbl');
    if (!tbl || tbl._sortDone) return;
    tbl._sortDone = true;
    var header = pd.getElementById('tbl-header-row');
    if (!header) return;
    var ths = header.querySelectorAll('th.sortable');
    var sortCol  = -1;
    var sortAsc  = true;

    ths.forEach(function(th, idx) {
      // Find absolute column index (header has non-sortable cols too)
      var allThs = Array.from(header.querySelectorAll('th'));
      var colIdx = allThs.indexOf(th);
      th.addEventListener('click', function() {
        if (sortCol === colIdx) { sortAsc = !sortAsc; }
        else { sortCol = colIdx; sortAsc = true; }
        // Update sort icons
        ths.forEach(function(t) {
          t.classList.remove('sort-asc','sort-desc');
          var ic = t.querySelector('.sort-icon');
          if (ic) ic.textContent = '⇅';
        });
        th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
        var ic = th.querySelector('.sort-icon');
        if (ic) ic.textContent = sortAsc ? '▲' : '▼';
        // Sort rows
        var tbody = tbl.querySelector('tbody');
        var rows  = Array.from(tbody.querySelectorAll('tr'));
        var dtype = th.dataset.dtype || 'str';
        rows.sort(function(a, b) {
          var aCell = a.querySelectorAll('td')[colIdx];
          var bCell = b.querySelectorAll('td')[colIdx];
          var aVal  = aCell ? (aCell.dataset.sort !== undefined ? aCell.dataset.sort : aCell.textContent.trim()) : '';
          var bVal  = bCell ? (bCell.dataset.sort !== undefined ? bCell.dataset.sort : bCell.textContent.trim()) : '';
          var cmp   = 0;
          if (dtype === 'num') {
            var an = parseFloat(aVal), bn = parseFloat(bVal);
            cmp = (isNaN(an) ? -Infinity : an) - (isNaN(bn) ? -Infinity : bn);
          } else {
            cmp = aVal.localeCompare(bVal);
          }
          return sortAsc ? cmp : -cmp;
        });
        rows.forEach(function(r) { tbody.appendChild(r); });
      });
    });
  }

  /* ── Fullscreen chart buttons ────────────────────────────────── */
  function addFullscreenBtns() {
    var pd = window.parent.document;
    pd.querySelectorAll('[data-testid="stPlotlyChart"]').forEach(function(el) {
      if (el._fsDone) return;
      el._fsDone = true;
      var btn = pd.createElement('button');
      btn.className = 'chart-fs-btn';
      btn.title     = 'Fullscreen (click again to exit)';
      btn.textContent = '⛶';
      btn.addEventListener('click', function(e) {
        e.stopPropagation();
        if (el.classList.contains('chart-fullscreen')) {
          el.classList.remove('chart-fullscreen');
          pd.body.style.overflow = '';
          btn.textContent = '⛶';
        } else {
          el.classList.add('chart-fullscreen');
          pd.body.style.overflow = 'hidden';
          btn.textContent = '✕';
        }
      });
      el.appendChild(btn);
    });
  }

  /* ── Star / watchlist clicks ─────────────────────────────────── */
  (function initStars() {
    var pd = window.parent.document;
    if (pd._starListenerDone) return;
    pd._starListenerDone = true;
    pd.addEventListener('click', function(e) {
      var star = e.target.closest('[data-star]');
      if (!star) return;
      e.preventDefault();
      e.stopPropagation();
      window.parent.location.href = '?star=' + encodeURIComponent(star.dataset.star);
    });
  })();

  /* ── Chip info toggles — JS-positioned (fixed) for mobile + desktop ─── */
  function initChipInfo() {
    var pd = window.parent.document;

    function closeAll() {
      pd.querySelectorAll('.chip-tip.open').forEach(function(t) { t.classList.remove('open'); });
    }

    function openTip(btn) {
      var tip = btn.closest('.chip-tip');
      if (!tip) return;
      var popup = tip.querySelector('.chip-info-popup');
      if (!popup) return;
      closeAll();
      // Position as fixed so it escapes any overflow/stacking-context parent
      var rect = btn.getBoundingClientRect();
      var pw = window.parent.innerWidth || 320;
      var left = Math.max(8, rect.left - 10);
      if (left + 270 > pw) left = Math.max(8, pw - 278);
      popup.style.top  = (rect.bottom + 8) + 'px';
      popup.style.left = left + 'px';
      tip.classList.add('open');
    }

    pd.querySelectorAll('.chip-info-btn').forEach(function(btn) {
      if (btn._ci) return; btn._ci = true;

      btn.addEventListener('click', function(e) {
        e.preventDefault(); e.stopPropagation();
        var tip = btn.closest('.chip-tip');
        var isOpen = tip && tip.classList.contains('open');
        closeAll();
        if (!isOpen) openTip(btn);
      });

      // Desktop hover via JS (popup is fixed so CSS hover positioning won't work)
      btn.addEventListener('mouseenter', function() { openTip(btn); });
      var tip = btn.closest('.chip-tip');
      if (tip) {
        tip.addEventListener('mouseleave', function() { closeAll(); });
      }
    });

    if (!pd._chipClose) {
      pd._chipClose = true;
      pd.addEventListener('click', function(e) {
        if (!e.target.closest('.chip-tip')) closeAll();
      });
      pd.addEventListener('touchend', function(e) {
        if (!e.target.closest('.chip-tip')) closeAll();
      }, {passive: true});
    }
  }

  /* ── Mobile: collapse long chart notes with Read-more toggle ─────────── */
  function initExpandNotes() {
    if (window.parent.innerWidth > 768) return;
    var pd = window.parent.document;
    pd.querySelectorAll('.chart-note:not([data-ei])').forEach(function(el) {
      el.setAttribute('data-ei', '1');
      if (el.scrollHeight <= 76) return;
      el.classList.add('note-truncated');
      var btn = pd.createElement('button');
      btn.className   = 'expand-note-btn';
      btn.textContent = 'Read more ↓';
      btn.addEventListener('click', function() {
        var collapsed = el.classList.toggle('note-truncated');
        btn.textContent = collapsed ? 'Read more ↓' : 'Show less ↑';
      });
      el.parentNode.insertBefore(btn, el.nextSibling);
    });
  }

  /* ── Zoom-reset text: reposition to bottom + match site style ───────── */
  function initZoomText() {
    var pd = window.parent.document;
    setInterval(function() {
      pd.querySelectorAll('.js-plotly-plot svg text').forEach(function(t) {
        if (t._zs) return;
        var txt = (t.textContent || '').toLowerCase();
        if (txt.indexOf('double') === -1 && txt.indexOf('reset') === -1) return;
        t._zs = true;
        t.setAttribute('fill', '#7A6A52');
        t.style.fontFamily = 'JetBrains Mono, monospace';
        t.style.fontSize   = '9px';
        var svg = t.closest('svg');
        if (svg) {
          var h = parseFloat(svg.getAttribute('height') || '200');
          t.setAttribute('y', String(Math.max(h - 10, 20)));
          t.setAttribute('text-anchor', 'middle');
        }
      });
    }, 600);
  }

  setTimeout(initTableSort, 600);
  setTimeout(initTableSort, 1500);
  setTimeout(addFullscreenBtns, 800);
  setTimeout(addFullscreenBtns, 2000);
  setTimeout(addFullscreenBtns, 4000);
  initChipInfo(); setTimeout(initChipInfo, 600);
  setTimeout(initExpandNotes, 1000); setTimeout(initExpandNotes, 2500);
  initZoomText();

})();
</script>
"""


# ── Chart builders ─────────────────────────────────────────────────────────────
def _apply_date_range(df, date_from, date_to):
    """Slice a datetime-indexed DataFrame to the given date range."""
    if date_from is not None:
        df = df[df.index >= pd.Timestamp(date_from)]
    if date_to is not None:
        df = df[df.index <= pd.Timestamp(date_to)]
    return df


def chart_price(ticker, date_from=None, date_to=None):
    df = load_prices(ticker)
    if df.empty:
        return None
    df = _apply_date_range(df, date_from, date_to)
    if df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["close_price"], mode="lines",
        line=dict(color=C1, width=3),
        fill="tozeroy", fillcolor="rgba(107,66,38,0.07)",
        name="Close", hovertemplate="$%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(**chart_layout(f"{ticker}  ·  Daily Close Price (USD)"))
    fig.update_yaxes(tickprefix="$")
    return fig


def chart_stocktwits(ticker, date_from=None, date_to=None):
    df = load_stocktwits(ticker)
    if df.empty or "bullish_count" not in df.columns:
        return None, True
    df = _apply_date_range(df.copy(), date_from, date_to)
    if df.empty:
        return None, True
    total       = df["message_count"].replace(0, np.nan)
    df["bull%"] = (df["bullish_count"] / total * 100).fillna(0)
    df["bear%"] = (df["bearish_count"] / total * 100).fillna(0)

    bull_n = norm_0_100(df["bull%"])
    bear_n = norm_0_100(df["bear%"])
    sparse = len(df) < 3
    mode   = "lines+markers" if sparse else "lines"

    fig = go.Figure()
    pn = _price_norm(ticker)
    if pn is not None:
        fig.add_trace(go.Scatter(
            x=pn.index, y=pn, mode="lines",
            line=dict(color=C2, width=2.5),
            name="Price (norm)", hovertemplate="%{y:.1f}<extra>Price (norm)</extra>",
        ))
    fig.add_trace(go.Scatter(
        x=bull_n.index, y=bull_n, mode=mode,
        line=dict(color=GREEN, width=2.5), marker=dict(size=6),
        fill="tozeroy", fillcolor="rgba(58,107,53,0.10)",
        name="Bullish (norm)", hovertemplate="%{y:.1f}<extra>Bullish</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=bear_n.index, y=bear_n, mode=mode,
        line=dict(color=RED, width=2.5), marker=dict(size=6),
        fill="tozeroy", fillcolor="rgba(155,58,40,0.08)",
        name="Bearish (norm)", hovertemplate="%{y:.1f}<extra>Bearish</extra>",
    ))

    title = f"{ticker}  ·  StockTwits Sentiment (normalized 0–100){_NORM_SUBTITLE}"
    layout = chart_layout(title)
    layout["yaxis"].update(
        range=[0, 105], tickvals=[0, 25, 50, 75, 100],
        title=dict(text="Normalized (0–100)", font=dict(size=9, color=MUTED)),
    )
    fig.update_layout(**layout)
    return fig, sparse


def chart_trends(ticker, date_from=None, date_to=None):
    df = load_trends(ticker)
    if df.empty:
        return None
    df = _apply_date_range(df, date_from, date_to)
    if df.empty:
        return None

    interest_n = norm_0_100(df["interest"])
    fig = go.Figure()
    pn = _price_norm(ticker)
    if pn is not None:
        fig.add_trace(go.Scatter(
            x=pn.index, y=pn, mode="lines",
            line=dict(color=C2, width=2.5),
            name="Price (norm)", hovertemplate="%{y:.1f}<extra>Price (norm)</extra>",
        ))
    fig.add_trace(go.Scatter(
        x=interest_n.index, y=interest_n, mode="lines",
        line=dict(color=C1, width=2.5),
        fill="tozeroy", fillcolor="rgba(107,66,38,0.07)",
        name="Search Interest (norm)", hovertemplate="%{y:.1f}<extra>Interest</extra>",
    ))

    if len(df) >= 7:
        mn, mx = df["interest"].min(), df["interest"].max()
        rolling_n = (
            (df["interest"].rolling(7, min_periods=1).mean() - mn) / (mx - mn) * 100
            if mx != mn else pd.Series(50.0, index=df.index)
        )
        fig.add_trace(go.Scatter(
            x=rolling_n.index, y=rolling_n, mode="lines",
            line=dict(color=BORDER, width=1.2, dash="dot"),
            name="7d avg (norm)", hovertemplate="%{y:.1f}<extra>7d avg</extra>",
        ))

    title = f"{ticker}  ·  Google Trends Search Interest (normalized 0–100){_NORM_SUBTITLE}"
    layout = chart_layout(title)
    layout["yaxis"].update(
        range=[0, 105], tickvals=[0, 25, 50, 75, 100],
        title=dict(text="Normalized (0–100)", font=dict(size=9, color=MUTED)),
    )
    fig.update_layout(**layout)
    return fig


def chart_news(ticker, date_from=None, date_to=None):
    df = load_news(ticker)
    if df.empty or "avg_sentiment" not in df.columns:
        return None, True
    df = _apply_date_range(df, date_from, date_to)
    if df.empty:
        return None, True

    sent = df["avg_sentiment"].dropna()
    if len(sent) < 1:
        return None, True
    sparse = len(sent) < 3

    sent_n = norm_0_100(sent)
    mn, mx = sent.min(), sent.max()
    neutral_pos = max(0.0, min(100.0, ((0 - mn) / (mx - mn) * 100) if mx != mn else 50.0))

    colors = [GREEN if v >= neutral_pos else RED for v in sent_n]
    fig = go.Figure()
    pn = _price_norm(ticker)
    if pn is not None:
        fig.add_trace(go.Scatter(
            x=pn.index, y=pn, mode="lines",
            line=dict(color=C2, width=2.5),
            name="Price (norm)", hovertemplate="%{y:.1f}<extra>Price (norm)</extra>",
        ))
    fig.add_trace(go.Bar(
        x=sent_n.index, y=sent_n, marker_color=colors,
        name="Sentiment (norm)",
        hovertemplate="%{y:.1f}<extra>Sentiment (norm)</extra>",
    ))
    fig.add_hline(y=neutral_pos, line_color=BORDER, line_width=1,
                  annotation_text="neutral",
                  annotation_font=dict(size=9, color=MUTED),
                  annotation_position="top right")

    title = f"{ticker}  ·  News Headline Sentiment (normalized 0–100){_NORM_SUBTITLE}"
    layout = chart_layout(title)
    layout["yaxis"].update(
        range=[0, 105], tickvals=[0, 25, 50, 75, 100],
        title=dict(text="Normalized (0–100)", font=dict(size=9, color=MUTED)),
    )
    fig.update_layout(**layout)
    return fig, sparse


def chart_wikipedia(ticker, date_from=None, date_to=None):
    wiki_df  = load_wikipedia(ticker)
    price_df = load_prices(ticker)
    wiki_df  = _apply_date_range(wiki_df, date_from, date_to)
    fig      = go.Figure()

    if wiki_df.empty or "page_views" not in wiki_df.columns:
        return None

    views = wiki_df["page_views"].dropna()
    if len(views) < 3:
        return None

    views_n = norm_0_100(np.log1p(views))   # log-scale to dampen viral spikes
    fig.add_trace(go.Scatter(
        x=views_n.index, y=views_n, mode="lines+markers",
        name="Wikipedia Views (log-norm)",
        line=dict(color=C5, width=2.5), marker=dict(size=5),
        hovertemplate="%{y:.1f}<extra>Wikipedia Views</extra>",
    ))

    if not price_df.empty:
        p = price_df["close_price"].dropna()
        if len(p) >= 2:
            fig.add_trace(go.Scatter(
                x=norm_0_100(p).index, y=norm_0_100(p),
                mode="lines", name="Price (norm)",
                line=dict(color=C2, width=2.5),
                hovertemplate="%{y:.1f}<extra>Price</extra>",
            ))

    title = f"{ticker}  ·  Wikipedia Page Views (log-normalized 0–100){_NORM_SUBTITLE}"
    layout = chart_layout(title)
    layout["yaxis"].update(
        range=[-5, 108], tickvals=[0, 25, 50, 75, 100],
        title=dict(text="Log-Normalized (0–100)", font=dict(size=9, color=MUTED)),
    )
    fig.update_layout(**layout)
    return fig


def chart_overlay(ticker, date_from=None, date_to=None):
    price_df  = _apply_date_range(load_prices(ticker),      date_from, date_to)
    trends_df = _apply_date_range(load_trends(ticker),      date_from, date_to)
    st_df     = _apply_date_range(load_stocktwits(ticker),  date_from, date_to)
    news_df   = _apply_date_range(load_news(ticker),        date_from, date_to)
    wiki_df   = _apply_date_range(load_wikipedia(ticker),   date_from, date_to)
    fig       = go.Figure()

    # Signals first — price drawn last so it sits on top
    if not trends_df.empty:
        n = norm_0_100(trends_df["interest"])
        fig.add_trace(go.Scatter(
            x=n.index, y=n, mode="lines", name="Trends",
            line=dict(color=C2, width=2),
            hovertemplate="%{y:.1f}<extra>Trends</extra>",
        ))
    if not st_df.empty and "net_sentiment" in st_df.columns:
        n = norm_0_100(st_df["net_sentiment"])
        fig.add_trace(go.Scatter(
            x=n.index, y=n, mode="lines+markers", name="StockTwits",
            line=dict(color=GREEN, width=2), marker=dict(size=5),
            hovertemplate="%{y:.1f}<extra>StockTwits</extra>",
        ))
    if not news_df.empty and "avg_sentiment" in news_df.columns:
        n = norm_0_100(news_df["avg_sentiment"])
        fig.add_trace(go.Scatter(
            x=n.index, y=n, mode="lines+markers", name="News",
            line=dict(color=C4, width=2), marker=dict(size=5),
            hovertemplate="%{y:.1f}<extra>News Sent.</extra>",
        ))
    if not wiki_df.empty and "page_views" in wiki_df.columns:
        views = wiki_df["page_views"].dropna()
        if len(views) >= 3:
            n = norm_0_100(np.log1p(views))
            fig.add_trace(go.Scatter(
                x=n.index, y=n, mode="lines", name="Wikipedia",
                line=dict(color=C5, width=2, dash="dashdot"),
                hovertemplate="%{y:.1f}<extra>Wikipedia Views</extra>",
            ))
    # Price LAST — most prominent, drawn on top of all signals
    if not price_df.empty:
        p = price_df["close_price"].dropna()
        if len(p) >= 2:
            pn = norm_0_100(p)
            fig.add_trace(go.Scatter(
                x=pn.index, y=pn, mode="lines",
                name="Price (norm)", line=dict(color=C1, width=3),
                hovertemplate="%{y:.1f}<extra>Price</extra>",
            ))

    layout = chart_layout(f"{ticker}  ·  All Signals Overlaid (normalized 0–100)", height=320)
    layout["yaxis"].update(
        range=[-5, 108], tickvals=[0, 25, 50, 75, 100],
        title=dict(text="Signal Strength (normalized)", font=dict(size=9, color=MUTED)),
    )
    fig.update_layout(**layout)
    return fig


# ── Sparkline SVG ──────────────────────────────────────────────────────────────
def build_sparkline_svg(ticker, sig_color):
    df = load_prices(ticker)
    if df.empty:
        return '<div class="spark-nodata">—</div>'
    prices = df["close_price"].dropna().tail(14).values
    if len(prices) < 2:
        return '<div class="spark-nodata">—</div>'

    W, H, PAD = 200, 48, 4
    mn, mx    = prices.min(), prices.max()

    if mx == mn:
        mid = H / 2
        d   = f"M {PAD},{mid:.1f} L {W - PAD},{mid:.1f}"
    else:
        n    = len(prices)
        step = (W - 2 * PAD) / (n - 1)
        pts  = [
            (PAD + i * step, PAD + (1 - (p - mn) / (mx - mn)) * (H - 2 * PAD))
            for i, p in enumerate(prices)
        ]
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    return (
        f'<div class="spark-svg-wrap">'
        f'<svg viewBox="0 0 {W} {H}" width="100%" height="48" '
        f'aria-hidden="true" style="display:block;overflow:visible;">'
        f'<path d="{d}" fill="none" stroke="{sig_color}" stroke-width="2.5" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'</svg></div>'
    )


def build_table_sparkline(ticker, sig_color, days=30):
    """Tiny 80×22px SVG sparkline for the summary table."""
    df = load_prices(ticker)
    if df.empty:
        return '<span style="color:var(--border)">—</span>'
    prices = df["close_price"].dropna().tail(days).values
    if len(prices) < 2:
        return '<span style="color:var(--border)">—</span>'
    W, H, PAD = 80, 22, 2
    mn, mx    = prices.min(), prices.max()
    if mx == mn:
        mid = H / 2
        d   = f"M {PAD},{mid:.1f} L {W - PAD},{mid:.1f}"
    else:
        n    = len(prices)
        step = (W - 2 * PAD) / (n - 1)
        pts  = [
            (PAD + i * step, PAD + (1 - (p - mn) / (mx - mn)) * (H - 2 * PAD))
            for i, p in enumerate(prices)
        ]
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return (
        f'<div class="tbl-spark">'
        f'<svg viewBox="0 0 {W} {H}" aria-hidden="true">'
        f'<path d="{d}" fill="none" stroke="{sig_color}" stroke-width="1.8" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'</svg></div>'
    )


# ── Sparkline card grid ────────────────────────────────────────────────────────
def _go_to_ticker(ticker):
    st.query_params["ticker"] = ticker

def show_sparkline_grid(rows):
    """Renders sparkline cards using st.columns so VIEW DETAILS uses st.button (no anchor tags)."""
    for row_start in range(0, len(rows), 4):
        batch = rows[row_start:row_start + 4]
        cols  = st.columns(4, gap="small")
        for col, r in zip(cols, batch):
            ticker    = r["ticker"]
            sig_color = r["sig_color"]
            delay_ms  = (row_start + batch.index(r)) * 80
            svg       = build_sparkline_svg(ticker, sig_color)
            with col:
                st.markdown(
                    f'<div class="spark-card" '
                    f'style="border-top-color:{sig_color};animation-delay:{delay_ms}ms">'
                    f'<div class="spark-card-top">'
                    f'<span class="spark-ticker">{ticker}</span>'
                    f'<span class="spark-sig" style="color:{sig_color}">{r["signal"]}</span>'
                    f'</div>'
                    f'{svg}'
                    f'<div class="spark-stats">'
                    f'<span class="spark-stat-label">Bullish</span>'
                    f'<span class="spark-stat-val">{r["bullish_pct"]}</span>'
                    f'<span class="spark-stat-label">News Sent.</span>'
                    f'<span class="spark-stat-val">{r["news_sent"]}</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.button(
                    "VIEW DETAILS",
                    key=f"sg_{ticker}",
                    use_container_width=True,
                    on_click=_go_to_ticker,
                    args=(ticker,),
                )


# ── Header ─────────────────────────────────────────────────────────────────────
def show_header():
    last_up     = get_last_updated()
    last_up_str = format_et(last_up) if last_up else date.today().strftime("%Y-%m-%d")

    # Hamburger + overlay + header in ONE st.markdown so there is no Streamlit
    # flex-gap above the dark band — components.html runs after, not before.
    st.markdown(f"""
    <button class="hamburger-btn" id="hamburger-btn" aria-label="Open menu">
      <span></span><span></span><span></span>
    </button>
    <div class="sidebar-overlay" id="sidebar-overlay"></div>
    <div class="rh">
      <button class="theme-toggle" id="theme-toggle" aria-label="Toggle dark/light mode">
        <span class="theme-toggle-icon" id="theme-icon">◑</span>
        <span id="theme-label">DARK</span>
      </button>
      <div class="rh-eyebrow">Alternative Data Research</div>
      <div class="rh-title">Alt Data Signal Tracker</div>
      <div class="rh-body">
        Tracking community sentiment, search interest, and news tone across {len(config.TICKERS)} consumer
        equities — collected daily and compared against closing prices to test whether alternative data
        sources lead or lag short-term stock price movements.
      </div>
      <div class="rh-status">
        <span class="status-active"></span>
        UPDATED {date.today().strftime('%Y-%m-%d')}
        &nbsp;&nbsp;·&nbsp;&nbsp;{len(config.TICKERS)} TICKERS
        &nbsp;&nbsp;·&nbsp;&nbsp;4 SIGNALS
        &nbsp;&nbsp;·&nbsp;&nbsp;PIPELINE ACTIVE · DAILY 06:30
        &nbsp;&nbsp;·&nbsp;&nbsp;SENTIMENT FROM 2026-06-22
      </div>
      <div class="rh-last-updated">
        <span class="lu-dot"></span>
        DATA LAST FETCHED: {last_up_str}
      </div>
    </div>
    """, unsafe_allow_html=True)
    components.html("""<script>
    (function(){
      var pd=window.parent.document;

      // ── Fix top gap ───────────────────────────────────────────────────────
      function _fixGap(){
        var targets=[
          pd.querySelector('.block-container'),
          pd.querySelector('[data-testid="stMainBlockContainer"]'),
          pd.querySelector('[data-testid="stMain"]'),
          pd.querySelector('[data-testid="stAppViewContainer"]'),
        ];
        targets.forEach(function(el){
          if(!el)return;
          el.style.setProperty('padding-top','0','important');
          el.style.setProperty('margin-top','0','important');
          el.style.setProperty('gap','0','important');
          el.style.setProperty('row-gap','0','important');
        });
        // Also zero out the first element-container gap/margin
        var firstEl = pd.querySelector('[data-testid="stMainBlockContainer"] > .element-container:first-child');
        if(firstEl){
          firstEl.style.setProperty('margin-top','0','important');
          firstEl.style.setProperty('padding-top','0','important');
        }
        // Only zero gap on the direct child stVerticalBlock (not all nested ones)
        var topVblock = pd.querySelector('[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]');
        if(topVblock){ topVblock.style.setProperty('gap','0','important'); }
      }
      _fixGap();
      setTimeout(_fixGap, 200);
      setTimeout(_fixGap, 600);

      // ── Style sidebar buttons to match the About/Predictions link style ──
      function _styleSidebarBtns(){
        var sb=pd.querySelector('[data-testid="stSidebar"]');
        if(!sb)return;
        var btns=sb.querySelectorAll('button');
        btns.forEach(function(btn){
          var txt=(btn.textContent||'').trim();
          // × remove buttons keep their own style
          if(txt==='×'||txt==='x'||btn.offsetWidth<40)return;
          btn.style.setProperty('background','transparent','important');
          btn.style.setProperty('border','1px solid rgba(139,111,71,0.4)','important');
          btn.style.setProperty('border-radius','6px','important');
          btn.style.setProperty('color','rgba(139,111,71,0.75)','important');
          btn.style.setProperty('font-family','JetBrains Mono,monospace','important');
          btn.style.setProperty('font-size','0.68rem','important');
          btn.style.setProperty('font-weight','400','important');
          btn.style.setProperty('letter-spacing','0.1em','important');
          btn.style.setProperty('text-transform','uppercase','important');
          btn.style.setProperty('text-align','center','important');
          btn.style.setProperty('width','100%','important');
          btn.style.setProperty('box-shadow','none','important');
          // center the wrapper
          var wrap = btn.closest('.stButton');
          if(wrap){
            wrap.style.setProperty('display','flex','important');
            wrap.style.setProperty('justify-content','center','important');
          }
          btn.onmouseenter=function(){
            this.style.setProperty('border-color','#8B6F47','important');
            this.style.setProperty('color','#8B6F47','important');
          };
          btn.onmouseleave=function(){
            this.style.setProperty('border-color','rgba(139,111,71,0.4)','important');
            this.style.setProperty('color','rgba(139,111,71,0.75)','important');
          };
        });
      }
      _styleSidebarBtns();
      setTimeout(_styleSidebarBtns, 300);
      setTimeout(_styleSidebarBtns, 900);

      // ── Hamburger toggle ──────────────────────────────────────────────────
      function _toggle(){
        var sb=pd.querySelector('[data-testid="stSidebar"]');
        if(!sb)return;
        var open=sb.classList.toggle('sidebar-open');
        var ov=pd.getElementById('sidebar-overlay');
        var bt=pd.getElementById('hamburger-btn');
        if(ov)ov.classList.toggle('active',open);
        if(bt)bt.classList.toggle('is-open',open);
        pd.body.style.overflow=open?'hidden':'';
      }
      window.parent.toggleSidebar=_toggle;
      function _bind(){
        var bt=pd.getElementById('hamburger-btn');
        var ov=pd.getElementById('sidebar-overlay');
        if(bt&&!bt._hb){
          bt._hb=true;
          bt.addEventListener('click',_toggle);
          bt.addEventListener('touchstart',function(e){e.preventDefault();_toggle();},{passive:false});
        }
        if(ov&&!ov._hb){
          ov._hb=true;
          ov.addEventListener('click',_toggle);
          ov.addEventListener('touchstart',function(e){e.preventDefault();_toggle();},{passive:false});
        }
      }
      window.parent.addEventListener('resize',function(){
        if(window.parent.innerWidth>768){
          var sb=pd.querySelector('[data-testid="stSidebar"]');
          var ov=pd.getElementById('sidebar-overlay');
          var bt=pd.getElementById('hamburger-btn');
          if(sb)sb.classList.remove('sidebar-open');
          if(ov)ov.classList.remove('active');
          if(bt)bt.classList.remove('is-open');
          pd.body.style.overflow='';
        }
      });
      _bind();
      setTimeout(_bind, 400);
      setTimeout(_bind, 1200);

      // ── Dark mode ────────────────────────────────────────────────────────
      function _applyTheme(dark){
        if(dark){
          pd.documentElement.setAttribute('data-theme','dark');
        } else {
          pd.documentElement.removeAttribute('data-theme');
        }
        var icon  = pd.getElementById('theme-icon');
        var label = pd.getElementById('theme-label');
        if(icon)  icon.textContent  = dark ? '☀' : '◑';
        if(label) label.textContent = dark ? 'LIGHT' : 'DARK';
        try { window.parent.localStorage.setItem('altdata_theme', dark ? 'dark' : 'light'); } catch(e){}
      }
      function _toggleTheme(){
        var isDark = pd.documentElement.getAttribute('data-theme') === 'dark';
        _applyTheme(!isDark);
      }
      // Bind theme toggle button via addEventListener (same pattern as hamburger)
      function _bindTheme(){
        var tb = pd.getElementById('theme-toggle');
        if(tb && !tb._th){
          tb._th = true;
          tb.addEventListener('click', _toggleTheme);
        }
      }
      _bindTheme();
      setTimeout(_bindTheme, 300);
      setTimeout(_bindTheme, 800);
      // Restore saved preference on every page load
      (function(){
        var saved;
        try { saved = window.parent.localStorage.getItem('altdata_theme'); } catch(e){}
        _applyTheme(saved === 'dark');
      })();

      // ── Watchlist — pure client-side, no page reload ─────────────────────
      function _wlGet() {
        try { return JSON.parse(window.parent.localStorage.getItem('altdata_watchlist') || '[]'); }
        catch(e) { return []; }
      }
      function _wlSave(wl) {
        try { window.parent.localStorage.setItem('altdata_watchlist', JSON.stringify(wl)); }
        catch(e) {}
      }
      function _wlApply() {
        var tbl = pd.getElementById('signal-tbl');
        if (!tbl) return;
        var tbody = tbl.querySelector('tbody');
        if (!tbody) return;
        var wl = _wlGet();
        // Update each star icon + row class
        pd.querySelectorAll('[data-star]').forEach(function(s) {
          var on = wl.indexOf(s.dataset.star) !== -1;
          s.textContent = on ? '★' : '☆';
          s.classList.toggle('starred', on);
          var row = s.closest('tr');
          if (row) row.classList.toggle('watchlisted', on);
        });
        // Move starred rows to top without reloading
        var rows = Array.from(tbody.querySelectorAll('tr'));
        var top  = rows.filter(function(r){ return r.classList.contains('watchlisted'); });
        var rest = rows.filter(function(r){ return !r.classList.contains('watchlisted'); });
        top.concat(rest).forEach(function(r){ tbody.appendChild(r); });
      }
      if (!pd._starListenerDone) {
        pd._starListenerDone = true;
        pd.addEventListener('click', function(e) {
          var star = e.target.closest('[data-star]');
          if (!star) return;
          e.preventDefault();
          e.stopPropagation();
          var ticker = star.dataset.star;
          var wl = _wlGet();
          var idx = wl.indexOf(ticker);
          if (idx !== -1) { wl.splice(idx, 1); }
          else { wl.unshift(ticker); }
          _wlSave(wl);
          _wlApply();
        });
      }
      // Restore watchlist state after every page render
      setTimeout(_wlApply, 400);
      setTimeout(_wlApply, 1000);

      // ── Info button tooltips (event delegation — survives rerenders) ──────
      // chip-fade-in animation ends with transform:none so position:fixed
      // popups are now viewport-relative, not market-chips-relative.
      if (!pd._ciDone) {
        pd._ciDone = true;
        function _ciClose() {
          pd.querySelectorAll('.chip-tip.open').forEach(function(t){ t.classList.remove('open'); });
        }
        function _ciOpen(btn, clientX, clientY) {
          var tip = btn.closest('.chip-tip');
          if (!tip) return;
          var pop = tip.querySelector('.chip-info-popup');
          if (!pop) return;
          _ciClose();
          var pw = window.parent.innerWidth || 320;
          var left = Math.max(8, clientX - 8);
          if (left + 300 > pw) left = Math.max(8, pw - 308);
          pop.style.top  = (clientY + 12) + 'px';
          pop.style.left = left + 'px';
          tip.classList.add('open');
        }
        pd.addEventListener('click', function(e) {
          var btn = e.target.closest('.chip-info-btn');
          if (btn) {
            e.preventDefault();
            var tip = btn.closest('.chip-tip');
            var wasOpen = tip && tip.classList.contains('open');
            _ciClose();
            if (!wasOpen) _ciOpen(btn, e.clientX, e.clientY);
            return;
          }
          if (!e.target.closest('.chip-tip')) _ciClose();
        });
        pd.addEventListener('mouseover', function(e) {
          var btn = e.target.closest('.chip-info-btn');
          if (btn) _ciOpen(btn, e.clientX, e.clientY);
        });
        pd.addEventListener('mouseout', function(e) {
          var from = e.target.closest && e.target.closest('.chip-tip');
          var to   = e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('.chip-tip');
          if (from && !to) _ciClose();
        });
      }

      // ── Zoom reset button (shown only when chart is zoomed) ───────────────
      function _initZoom() {
        pd.querySelectorAll('.js-plotly-plot').forEach(function(plot) {
          if (plot._zrDone) return;
          plot._zrDone = true;
          var container = plot.closest('[data-testid="stPlotlyChart"]');
          if (!container || !container.parentNode) return;
          var btn = pd.createElement('button');
          btn.className = 'zoom-reset-btn';
          btn.textContent = '↺ reset zoom';
          container.parentNode.insertBefore(btn, container.nextSibling);
          plot.on('plotly_relayout', function(ev) {
            if (!ev) return;
            var zoomed = 'xaxis.range[0]' in ev || 'xaxis.range' in ev;
            var reset  = ev['xaxis.autorange'] === true;
            if (zoomed) btn.classList.add('visible');
            if (reset)  btn.classList.remove('visible');
          });
          btn.addEventListener('click', function() {
            var Plt = window.parent.Plotly || window.Plotly;
            if (Plt) try { Plt.relayout(plot, {'xaxis.autorange':true,'yaxis.autorange':true}); } catch(e){}
            btn.classList.remove('visible');
          });
        });
      }
      setInterval(_initZoom, 2000);
      setTimeout(_initZoom, 800);

      // ── Sector heatmap card → filter + scroll to signal table ────────────
      // Uses event delegation on pd (same reliable pattern as stars + chip info).
      // No inline onclick needed — avoids React/CSP restrictions in st.markdown.
      if (!pd._shFilterDone) {
        pd._shFilterDone = true;
        pd.addEventListener('click', function(e) {
          var card = e.target.closest('.sh-cell');
          if (!card) return;
          e.preventDefault();

          var wasActive = card.classList.contains('sh-active');
          pd.querySelectorAll('.sh-cell').forEach(function(c) {
            c.classList.remove('sh-active');
          });

          var tbl = pd.getElementById('signal-tbl');
          if (!tbl) return;
          var rows = tbl.querySelectorAll('tbody tr');

          if (wasActive) {
            rows.forEach(function(r) { r.style.display = ''; });
          } else {
            card.classList.add('sh-active');
            var tickers = (card.getAttribute('data-tickers') || '').split(',').map(function(t) { return t.trim(); });
            rows.forEach(function(r) {
              var tc = r.querySelector('.tkr');
              var ticker = tc ? tc.textContent.trim() : '';
              r.style.display = (tickers.indexOf(ticker) !== -1) ? '' : 'none';
            });
          }

          try {
            var rect = tbl.getBoundingClientRect();
            window.parent.scrollTo({top: window.parent.pageYOffset + rect.top - 80, behavior: 'smooth'});
          } catch(ex) {}
        });
      }

    })();
    </script>""", height=0)


# ── Sector mapping ─────────────────────────────────────────────────────────────
SECTORS = {
    "Mega-Cap Tech":     ["AAPL", "NVDA", "AMZN", "MSFT", "GOOGL", "PLTR"],
    "Social / Media":    ["META", "SNAP", "PINS", "RDDT", "SPOT", "NFLX", "DIS", "UBER"],
    "Fintech / Finance": ["JPM", "GS", "HOOD", "PYPL", "SQ", "SOFI"],
    "Crypto":            ["COIN", "MSTR"],
    "EV & Auto":         ["TSLA", "RIVN", "LCID", "F", "GM"],
    "Retail & Consumer": ["WMT", "TGT", "MCD", "CHWY", "NKE", "ABNB", "SBUX"],
    "Defense & Space":   ["RKLB", "LMT", "RTX", "BA"],
    "Biotech & Pharma":  ["PFE", "MRNA", "NVAX"],
    "Quantum / Tech":    ["IONQ", "QBTS", "RGTI"],
    "Energy":            ["XOM", "CVX", "FSLR"],
    "Meme / Gaming":     ["GME", "AMC"],
    "ETF":               ["SPCX"],
}

SECTORS_GICS = {
    "Technology":             ["AAPL", "NVDA", "MSFT", "PLTR", "MSTR", "IONQ", "QBTS", "RGTI"],
    "Comm. Services":         ["GOOGL", "META", "SNAP", "PINS", "RDDT", "SPOT", "NFLX", "DIS"],
    "Consumer Discretionary": ["AMZN", "TSLA", "SBUX", "GME", "AMC", "CHWY", "NKE", "ABNB", "UBER", "RIVN", "LCID", "F", "GM"],
    "Consumer Staples":       ["WMT", "TGT", "MCD"],
    "Financials":             ["JPM", "GS", "HOOD", "PYPL", "SQ", "SOFI", "COIN"],
    "Healthcare":             ["PFE", "MRNA", "NVAX"],
    "Industrials & Defense":  ["LMT", "RTX", "BA", "RKLB"],
    "Energy":                 ["XOM", "CVX", "FSLR"],
    "Other":                  ["SPCX"],
}

# ── Analysis helpers ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_correlations_all():
    p = DATA_DIR / "correlations_all.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


def _pearson_pvalue(r, n):
    """Two-tailed p-value for Pearson r (uses normal approximation, good for n > 20)."""
    if n < 3 or abs(r) >= 1.0 - 1e-12:
        return 1.0
    t = r * math.sqrt(n - 2) / math.sqrt(max(1e-12, 1.0 - r * r))
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t) / math.sqrt(2.0))))
    return float(p)


@st.cache_data(ttl=300)
def build_historical_signals(ticker):
    """Daily composite-signal series built from available history."""
    price_df  = load_prices(ticker)
    trends_df = load_trends(ticker)
    st_df     = load_stocktwits(ticker)
    news_df   = load_news(ticker)

    if price_df.empty:
        return pd.DataFrame()

    price_s = price_df["close_price"].dropna().sort_index()
    df = pd.DataFrame({"close": price_s})
    df["pct_chg"] = price_s.pct_change() * 100

    # Google Trends vote
    if not trends_df.empty and "interest" in trends_df.columns:
        tr = trends_df["interest"].reindex(df.index, method="ffill", tolerance=pd.Timedelta("3d"))
        tr_avg = tr.rolling(7, min_periods=1).mean()
        df["trends_v"] = np.where(tr > tr_avg * 1.1, 1, np.where(tr < tr_avg * 0.9, -1, 0))
    else:
        df["trends_v"] = 0.0

    # Price vote
    df["price_v"] = np.where(df["pct_chg"] > 0.5, 1, np.where(df["pct_chg"] < -0.5, -1, 0))

    # StockTwits vote (sparse — typically only a few days)
    if not st_df.empty and {"bullish_count", "message_count"}.issubset(st_df.columns):
        valid = st_df.dropna(subset=["message_count"])
        valid = valid[valid["message_count"] > 0].copy()
        valid["bull_pct"] = valid["bullish_count"] / valid["message_count"] * 100
        bull_s = valid["bull_pct"].reindex(df.index, method="ffill", tolerance=pd.Timedelta("2d"))
        df["st_v"] = np.where(bull_s > 55, 1, np.where(bull_s < 40, -1, np.where(bull_s.isna(), 0, 0)))
    else:
        df["st_v"] = 0.0

    # News vote (sparse)
    if not news_df.empty and "avg_sentiment" in news_df.columns:
        ns = news_df["avg_sentiment"].reindex(df.index, method="ffill", tolerance=pd.Timedelta("2d")).fillna(0)
        df["news_v"] = np.where(ns > 0.1, 1, np.where(ns < -0.1, -1, 0))
    else:
        df["news_v"] = 0.0

    df["score"] = df["trends_v"] + df["price_v"] + df["st_v"] + df["news_v"]
    df["signal"] = np.where(df["score"] >= 2, "BULLISH",
                   np.where(df["score"] <= -2, "BEARISH", "NEUTRAL"))
    return df.dropna(subset=["close"])


# ── Fear & Greed Index ─────────────────────────────────────────────────────────
def compute_fear_greed(rows):
    """Return (score 0-100, label, dict of components)."""
    total = len(rows)
    if total == 0:
        return 50.0, "Neutral", {}

    bullish_n = sum(1 for r in rows if r["signal"] == "BULLISH")
    bearish_n = sum(1 for r in rows if r["signal"] == "BEARISH")
    up_n      = sum(1 for r in rows if r.get("chg_raw") is not None and r["chg_raw"] > 0)

    breadth   = bullish_n / total * 100
    momentum  = up_n / total * 100

    news_vals = [r["news_sent_raw"] for r in rows if r["news_sent_raw"] is not None]
    news_comp = (sum(news_vals) / len(news_vals) / 0.3 * 50 + 50) if news_vals else 50.0
    news_comp = max(0.0, min(100.0, news_comp))

    # Trends: % of tickers where latest trends > 50 (above mid-range)
    trends_above = 0
    trends_total = 0
    for ticker in config.TICKERS:
        tdf = load_trends(ticker)
        if not tdf.empty and "interest" in tdf.columns:
            val = tdf["interest"].dropna()
            if len(val) > 0:
                trends_total += 1
                if float(val.iloc[-1]) > float(val.mean()):
                    trends_above += 1
    trend_comp = (trends_above / trends_total * 100) if trends_total > 0 else 50.0

    components = {
        "Signal Breadth":   breadth,
        "Price Momentum":   momentum,
        "News Sentiment":   news_comp,
        "Search Interest":  trend_comp,
    }
    score = sum(components.values()) / len(components)

    if score < 25:
        label = "Extreme Fear"
    elif score < 45:
        label = "Fear"
    elif score < 55:
        label = "Neutral"
    elif score < 75:
        label = "Greed"
    else:
        label = "Extreme Greed"

    return round(score, 1), label, components


def build_fear_greed_gauge(score, label, components):
    fg_color = (RED if score < 25 else C2 if score < 45 else MUTED if score < 55 else C4 if score < 75 else GREEN)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"size": 36, "color": fg_color, "family": "DM Serif Display"}, "suffix": ""},
        title={"text": f"Fear & Greed<br><sup style='font-size:13px'>{label}</sup>",
               "font": {"size": 13, "color": MUTED, "family": "Inter"}},
        gauge={
            "axis": {"range": [0, 100], "tickfont": {"size": 9, "family": "JetBrains Mono", "color": MUTED},
                     "tickvals": [0, 25, 50, 75, 100]},
            "bar": {"color": fg_color, "thickness": 0.25},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 25],  "color": "rgba(155,58,40,0.18)"},
                {"range": [25, 45], "color": "rgba(196,125,62,0.18)"},
                {"range": [45, 55], "color": "rgba(122,106,82,0.12)"},
                {"range": [55, 75], "color": "rgba(160,137,107,0.18)"},
                {"range": [75, 100],"color": "rgba(58,107,53,0.20)"},
            ],
        }
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color=MUTED),
        height=200,
        margin=dict(l=20, r=20, t=60, b=10),
    )
    return fig


# ── Tab: Correlation Matrix ─────────────────────────────────────────────────────
_SIG_LABELS = {
    "google_trends":   "Google Trends",
    "wikipedia_views": "Wikipedia Views",
    "stocktwits_sent": "StockTwits Sent.",
    "news_sent":       "News Sentiment",
}

def tab_correlation_matrix():
    tab_intro(
        "Does today's social buzz predict tomorrow's stock price? Each cell shows how strongly "
        "a signal (rows) correlates with a stock's price return 1–3 days later (columns). "
        "Darker green = the signal tends to lead price higher. Darker red = it tends to lead price lower. "
        "Use the dropdown to change how many days ahead you're looking."
    )
    corr_df = load_correlations_all()
    if corr_df.empty:
        st.info("No correlation data yet — run the pipeline to generate correlations_all.csv.")
        return

    lag = st.selectbox(
        "Forward lag (days)",
        options=[1, 2, 3],
        index=0,
        help="lag=1: does today's signal predict tomorrow's price return?",
        key="cm_lag",
    )

    filt = corr_df[corr_df["lag"] == lag]
    if filt.empty:
        st.info(f"No data for lag = {lag}.")
        return

    pivot = filt.pivot_table(index="ticker", columns="signal", values="correlation")
    sig_order = [s for s in ["google_trends", "wikipedia_views", "stocktwits_sent", "news_sent"]
                 if s in pivot.columns]
    pivot = pivot[sig_order]
    col_labels = [_SIG_LABELS.get(c, c) for c in sig_order]

    n_all      = len(pivot)
    show_all   = st.session_state.get("cm_show_all", False)
    pivot_disp = pivot if (show_all or n_all <= 10) else pivot.iloc[:10]

    zvals = pivot_disp.values.tolist()
    text  = [[f"{v:.3f}" if not math.isnan(v) else "—" for v in row] for row in pivot_disp.values.tolist()]

    fig = go.Figure(go.Heatmap(
        z=zvals, x=col_labels, y=pivot_disp.index.tolist(),
        colorscale=[[0, RED], [0.5, SURFACE], [1, GREEN]],
        zmid=0, zmin=-0.5, zmax=0.5,
        text=text, texttemplate="%{text}",
        textfont=dict(size=8, family="JetBrains Mono"),
        hovertemplate="<b>%{y}</b> · %{x}<br>r = %{z:.3f}<extra></extra>",
        colorbar=dict(
            title=dict(text="Pearson r", side="right"),
            tickfont=dict(size=9, family="JetBrains Mono"),
            len=0.8,
        ),
    ))
    h = max(360, len(pivot_disp) * 18 + 80)
    layout = chart_layout(f"Signal → {lag}-Day Forward Return Correlation  ·  All Tickers", height=h)
    layout["xaxis"].update(side="top")
    layout["yaxis"].update(autorange="reversed")
    layout["margin"] = dict(l=72, r=24, t=72, b=20)
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    note(
        f"Each cell is the Pearson correlation between that signal on day t and the stock's "
        f"price return {lag} day(s) later. Green = signal predicts gains; red = signal predicts losses; "
        f"white = no relationship. StockTwits and News columns appear once 30+ days of data accumulate."
    )

    if n_all > 10:
        btn_lbl = f"Show all {n_all} tickers ↓" if not show_all else "Collapse to 10 ↑"
        if st.button(btn_lbl, key="cm_expand_btn"):
            st.session_state["cm_show_all"] = not show_all
            st.rerun()


# ── Tab: Lag Analysis ──────────────────────────────────────────────────────────
def tab_lag_analysis():
    tab_intro(
        "Pick a stock to see whether its alt-data signals tend to move before or after the price. "
        "A bar to the right means that signal led the price move — it fired first. "
        "Taller bars = stronger predictive relationship. This helps identify which signals are most useful as early warnings for a given stock."
    )
    corr_df = load_correlations_all()
    if corr_df.empty:
        st.info("No lag data yet — run the pipeline first.")
        return

    available = sorted(corr_df["ticker"].unique().tolist())
    def_idx   = available.index("AAPL") if "AAPL" in available else 0
    ticker    = st.selectbox("Select ticker", available, index=def_idx, key="lag_ticker")

    sub = corr_df[corr_df["ticker"] == ticker].copy()
    if sub.empty:
        st.info(f"No data for {ticker}.")
        return

    sub["pvalue"] = sub.apply(
        lambda r: _pearson_pvalue(float(r["correlation"]), int(r["n_obs"])), axis=1
    )
    sub["stars"] = sub["pvalue"].apply(
        lambda p: "***" if p < 0.01 else ("**" if p < 0.05 else ("*" if p < 0.10 else ""))
    )

    sig_colors = {
        "google_trends":   C2,
        "wikipedia_views": C5,
        "stocktwits_sent": GREEN,
        "news_sent":       C4,
    }

    fig = go.Figure()
    for sig in sub["signal"].unique():
        chunk = sub[sub["signal"] == sig].sort_values("lag")
        color = sig_colors.get(sig, ACCENT)
        fig.add_trace(go.Bar(
            name=_SIG_LABELS.get(sig, sig),
            x=chunk["lag"].tolist(),
            y=chunk["correlation"].tolist(),
            text=chunk["stars"].tolist(),
            textposition="outside",
            textfont=dict(size=12, color=TEXT),
            marker_color=color, marker_opacity=0.85,
            hovertemplate=(
                "<b>" + _SIG_LABELS.get(sig, sig) + "</b><br>"
                "Lag: %{x}d<br>r = %{y:.4f}<extra></extra>"
            ),
        ))

    layout = chart_layout(
        f"{ticker}  ·  Lag Analysis  "
        "(lag < 0 = signal follows price | lag > 0 = signal predicts price)",
        height=380,
    )
    layout["barmode"] = "group"
    layout["xaxis"].update(
        tickvals=list(range(-3, 4)),
        ticktext=["−3d", "−2d", "−1d", "Today", "+1d", "+2d", "+3d"],
        title=dict(text="Lag (days)", font=dict(size=10, color=MUTED)),
    )
    layout["yaxis"].update(
        zeroline=True, zerolinecolor=BORDER, zerolinewidth=1.5,
        title=dict(text="Pearson r", font=dict(size=10, color=MUTED)),
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    note(
        "<strong>P-value markers:</strong> *** p&lt;0.01 · ** p&lt;0.05 · * p&lt;0.10 — shown above each bar. "
        "Positive lag = signal leads price (predictive). Negative lag = price already moved (reactive). "
        "Normal approximation used; more reliable with 30+ observations."
    )

    with st.expander("Raw lag data table"):
        tbl = sub[["signal", "lag", "correlation", "n_obs", "pvalue", "stars"]].copy()
        tbl["signal"] = tbl["signal"].map(_SIG_LABELS).fillna(tbl["signal"])
        tbl.columns   = ["Signal", "Lag", "Correlation", "N", "P-Value", "Sig."]
        tbl = tbl.sort_values(["Signal", "Lag"])
        st.dataframe(
            tbl.style.format({"Correlation": "{:.4f}", "P-Value": "{:.4f}"}),
            hide_index=True, use_container_width=True,
        )


# ── Tab: Backtesting ────────────────────────────────────────────────────────────
def tab_backtesting():
    tab_intro(
        "Tests a simple rule on historical data: go long when the composite signal is BULLISH, "
        "sit in cash when BEARISH, and hold when NEUTRAL. "
        "The chart compares that strategy's growth against simply holding the stock the whole time. "
        "This is not investment advice — it shows whether the signals would have been useful in the past."
    )
    ticker = st.selectbox("Select ticker to backtest", config.TICKERS, index=0, key="bt_ticker")

    df = build_historical_signals(ticker)
    if df.empty or len(df) < 5:
        st.info("Not enough price data to backtest.")
        return

    # Strategy: long when BULLISH, cash when BEARISH, hold when NEUTRAL
    df = df.copy()
    df["daily_ret"] = df["close"].pct_change()

    # Position: enter after signal day (next day), so shift signal by 1
    df["pos"] = df["signal"].shift(1).map({"BULLISH": 1.0, "BEARISH": 0.0, "NEUTRAL": None})
    df["pos"] = df["pos"].ffill().fillna(1.0)  # neutral = hold last position; start fully invested

    df["strat_ret"]  = df["pos"] * df["daily_ret"]
    df["cum_strat"]  = (1 + df["strat_ret"].fillna(0)).cumprod()
    df["cum_hold"]   = (1 + df["daily_ret"].fillna(0)).cumprod()

    # SPY for comparison
    spy_df = fetch_yf_history("SPY")
    spy_cum = None
    if not spy_df.empty:
        spy_r = spy_df["close_price"].pct_change()
        spy_r = spy_r.reindex(df.index, method="nearest", tolerance=pd.Timedelta("2d"))
        spy_cum = (1 + spy_r.fillna(0)).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=(df["cum_strat"] - 1) * 100,
        name="Signal Strategy", mode="lines",
        line=dict(color=GREEN, width=2.5),
        hovertemplate="Strategy: %{y:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=(df["cum_hold"] - 1) * 100,
        name=f"Buy & Hold {ticker}", mode="lines",
        line=dict(color=C1, width=2, dash="dot"),
        hovertemplate="Buy & Hold: %{y:.1f}%<extra></extra>",
    ))
    if spy_cum is not None:
        fig.add_trace(go.Scatter(
            x=spy_cum.index, y=(spy_cum - 1) * 100,
            name="SPY (benchmark)", mode="lines",
            line=dict(color=C5, width=1.8, dash="dash"),
            hovertemplate="SPY: %{y:.1f}%<extra></extra>",
        ))

    strat_ret_total = float((df["cum_strat"].iloc[-1] - 1) * 100)
    hold_ret_total  = float((df["cum_hold"].iloc[-1] - 1) * 100)

    layout = chart_layout(
        f"{ticker}  ·  Signal Strategy vs Buy & Hold vs SPY  (cumulative return %)",
        height=360,
    )
    layout["yaxis"].update(ticksuffix="%", title=dict(text="Cumulative Return", font=dict(size=10, color=MUTED)))
    layout["yaxis"]["zeroline"]      = True
    layout["yaxis"]["zerolinecolor"] = BORDER
    layout["yaxis"]["zerolinewidth"] = 1.5
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    m1, m2, m3 = st.columns(3)
    with m1:
        delta = strat_ret_total - hold_ret_total
        st.metric("Strategy Return", f"{strat_ret_total:+.1f}%", f"{delta:+.1f}% vs hold")
    with m2:
        st.metric("Buy & Hold Return", f"{hold_ret_total:+.1f}%")
    with m3:
        if spy_cum is not None:
            spy_total = float((spy_cum.iloc[-1] - 1) * 100)
            st.metric("SPY Return", f"{spy_total:+.1f}%")

    note(
        "Strategy: go long when composite signal = BULLISH; move to cash when BEARISH; hold last position when NEUTRAL. "
        "Signals use Google Trends (90 days) + prior-day price change — StockTwits &amp; News activate as more data accumulates. "
        "No transaction costs. Past performance doesn't predict future returns."
    )


# ── Tab: Signal Accuracy Scorecard ─────────────────────────────────────────────
def tab_signal_accuracy():
    tab_intro(
        "A report card for each signal source. For every BULLISH or BEARISH call made historically, "
        "this checks whether the stock's price actually moved in that direction 7 days later. "
        "A hit rate above 50% means the signal was right more often than wrong. "
        "Higher = more reliable. Results improve as more data accumulates over time."
    )
    _NOTE_DAYS = 7

    rows_out = []
    for ticker in config.TICKERS:
        df = build_historical_signals(ticker)
        if df.empty or len(df) < _NOTE_DAYS + 2:
            continue

        price = df["close"]
        fwd_ret = price.shift(-_NOTE_DAYS) / price - 1

        for sig_name, vote_col in [
            ("Google Trends", "trends_v"),
            ("Price Momentum", "price_v"),
            ("StockTwits",     "st_v"),
            ("News Sent.",     "news_v"),
        ]:
            if vote_col not in df.columns:
                continue
            bull_mask = (df[vote_col] == 1)
            bear_mask = (df[vote_col] == -1)
            n_bull = int(bull_mask.sum())
            n_bear = int(bear_mask.sum())

            if n_bull >= 3:
                hit = float((fwd_ret[bull_mask] > 0).mean() * 100)
                rows_out.append({"Signal": sig_name, "Ticker": ticker,
                                 "Direction": "BULLISH", "N Calls": n_bull, "Hit Rate %": hit})
            if n_bear >= 3:
                hit = float((fwd_ret[bear_mask] < 0).mean() * 100)
                rows_out.append({"Signal": sig_name, "Ticker": ticker,
                                 "Direction": "BEARISH", "N Calls": n_bear, "Hit Rate %": hit})

    if not rows_out:
        st.info("Not enough historical signal + price data yet. Check back after 30+ days of accumulation.")
        return

    agg = (
        pd.DataFrame(rows_out)
        .groupby(["Signal", "Direction"])
        .agg(Avg_Hit_Rate=("Hit Rate %", "mean"), N_Tickers=("Ticker", "nunique"))
        .reset_index()
    )
    agg["Avg_Hit_Rate"] = agg["Avg_Hit_Rate"].round(1)

    signals = agg["Signal"].unique().tolist()
    directions = ["BULLISH", "BEARISH"]
    dir_colors = {"BULLISH": GREEN, "BEARISH": RED}

    fig = go.Figure()
    for direction in directions:
        sub = agg[agg["Direction"] == direction]
        fig.add_trace(go.Bar(
            name=direction,
            x=sub["Signal"].tolist(),
            y=sub["Avg_Hit_Rate"].tolist(),
            marker_color=dir_colors[direction],
            marker_opacity=0.85,
            text=[f"{v:.0f}%" for v in sub["Avg_Hit_Rate"].tolist()],
            textposition="outside",
            hovertemplate=(
                f"<b>{direction}</b><br>%{{x}}<br>Avg hit rate: %{{y:.1f}}%<extra></extra>"
            ),
        ))

    fig.add_hline(y=50, line_color=BORDER, line_dash="dash", line_width=1,
                  annotation_text="random (50%)", annotation_font=dict(size=9, color=MUTED))

    layout = chart_layout(
        f"Signal Accuracy — % of {_NOTE_DAYS}-Day Calls That Were Correct  (avg across all tickers)",
        height=360,
    )
    layout["barmode"] = "group"
    layout["yaxis"].update(range=[0, 115], ticksuffix="%",
                           title=dict(text="Hit Rate", font=dict(size=10, color=MUTED)))
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    note(
        f"For each signal, this shows what % of BULLISH calls were followed by a positive {_NOTE_DAYS}-day return "
        f"and what % of BEARISH calls were followed by a negative {_NOTE_DAYS}-day return, averaged across all tickers. "
        f"50% = random. Requires ≥3 signal events per ticker to include."
    )

    with st.expander("Per-ticker breakdown"):
        detail = pd.DataFrame(rows_out).round(1)
        st.dataframe(detail.sort_values(["Signal", "Hit Rate %"], ascending=[True, False]),
                     hide_index=True, use_container_width=True)


# ── Tab: Sector Heatmap ─────────────────────────────────────────────────────────
def tab_sector_heatmap(rows):
    rows_by_ticker = {r["ticker"]: r for r in rows}

    grouping = st.radio(
        "Group by", ["Custom Themes", "GICS / Classic"],
        horizontal=True, key="sh_grouping", label_visibility="collapsed",
    )
    sectors_map = SECTORS if grouping == "Custom Themes" else SECTORS_GICS

    sector_data = []
    for sector, tickers in sectors_map.items():
        for ticker in tickers:
            r = rows_by_ticker.get(ticker)
            if r is None:
                continue
            sig = r["signal"]
            sig_num = 1 if sig == "BULLISH" else (-1 if sig == "BEARISH" else 0)
            sector_data.append({
                "sector":  sector,
                "ticker":  ticker,
                "signal":  sig,
                "sig_num": sig_num,
                "chg":     r.get("chg_raw") or 0.0,
            })

    if not sector_data:
        st.info("No signal data available.")
        return

    agg = (
        pd.DataFrame(sector_data)
        .groupby("sector")
        .agg(avg_sig=("sig_num", "mean"), n_bull=("signal", lambda x: (x == "BULLISH").sum()),
             n_bear=("signal", lambda x: (x == "BEARISH").sum()), count=("ticker", "count"))
        .reset_index()
    )

    # Preserve dict insertion order for grid layout
    sector_order = list(sectors_map.keys())
    agg["_ord"] = agg["sector"].map({s: i for i, s in enumerate(sector_order)})
    agg = agg.sort_values("_ord").drop(columns="_ord")

    # Build per-sector ticker lists with signal colors
    sector_tickers = {}
    for item in sector_data:
        sect = item["sector"]
        if sect not in sector_tickers:
            sector_tickers[sect] = []
        sector_tickers[sect].append((item["ticker"], item["signal"]))

    cells = []
    for _, row in agg.iterrows():
        s = row["avg_sig"]
        if s >= 0.6:
            cls = "sh-strong-bull"
        elif s >= 0.2:
            cls = "sh-bull"
        elif s <= -0.6:
            cls = "sh-strong-bear"
        elif s <= -0.2:
            cls = "sh-bear"
        else:
            cls = "sh-neut"
        n_tot = int(row["count"])
        n_b   = int(row["n_bull"])
        n_be  = int(row["n_bear"])
        n_n   = n_tot - n_b - n_be
        bull_w = int(round(n_b  / n_tot * 100)) if n_tot else 0
        bear_w = int(round(n_be / n_tot * 100)) if n_tot else 0

        if s >= 0.2:
            badge_cls, badge_txt = "sh-badge-bull", "BULLISH"
        elif s <= -0.2:
            badge_cls, badge_txt = "sh-badge-bear", "BEARISH"
        else:
            badge_cls, badge_txt = "sh-badge-neut", "NEUTRAL"

        tick_spans = []
        ticker_list = []
        for t, sig in sector_tickers.get(row["sector"], []):
            tc = ("sh-tick-bull" if sig == "BULLISH"
                  else "sh-tick-bear" if sig == "BEARISH"
                  else "sh-tick-neut")
            tick_spans.append(f'<span class="{tc}">{t}</span>')
            ticker_list.append(t)

        tickers_attr = ",".join(ticker_list)
        cells.append(
            f'<a class="sh-cell {cls}" href="javascript:void(0)" data-tickers="{tickers_attr}">'
            f'<div class="sh-header">'
            f'<span class="sh-name">{row["sector"]}</span>'
            f'<span class="sh-badge {badge_cls}">{badge_txt}</span>'
            f'</div>'
            f'<div class="sh-tally">{n_b}B · {n_be}Be · {n_n}N of {n_tot}</div>'
            f'<div class="sh-tickers">{"".join(tick_spans)}</div>'
            f'<div class="sh-bar">'
            f'<div class="sh-fill-b" style="width:{bull_w}%"></div>'
            f'<div class="sh-fill-be" style="width:{bear_w}%"></div>'
            f'</div>'
            f'</a>'
        )

    st.markdown(
        f'<p class="sh-title">SECTOR SENTIMENT HEATMAP — COMPOSITE SIGNAL TODAY</p>'
        f'<div class="sh-grid">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )

    note(
        "Each card shows the sector's average composite signal. "
        "Ticker colours: green = BULLISH · red = BEARISH · grey = NEUTRAL. "
        "Bar = bullish share (green) vs bearish share (red). "
        "Click any card to filter the signal table to that sector — click again to clear."
    )


# ── Tab: Signal Divergence Detector ───────────────────────────────────────────
def tab_divergence_detector(rows):
    tab_intro(
        "Spots stocks where social media sentiment and news headlines are pointing in opposite directions. "
        "When people on StockTwits are bullish but news coverage is negative (or vice versa), "
        "it can signal a potential turning point or a crowd reaction that may not be justified. "
        "These mismatches are worth watching closely."
    )
    rows_by_ticker = {r["ticker"]: r for r in rows}

    divergences = []
    for ticker in config.TICKERS:
        st_df   = load_stocktwits(ticker)
        news_df = load_news(ticker)

        st_sent = None
        if not st_df.empty and {"bullish_count", "message_count"}.issubset(st_df.columns):
            valid = st_df.dropna(subset=["message_count"])
            valid = valid[valid["message_count"] > 0]
            if len(valid) > 0:
                last = valid.iloc[-1]
                bull_pct = last["bullish_count"] / last["message_count"] * 100
                st_sent = "BULLISH" if bull_pct > 55 else ("BEARISH" if bull_pct < 40 else "NEUTRAL")

        news_sent_val = None
        news_sig = None
        if not news_df.empty and "avg_sentiment" in news_df.columns:
            vs = news_df["avg_sentiment"].dropna()
            if len(vs) > 0:
                news_sent_val = float(vs.iloc[-1])
                news_sig = "BULLISH" if news_sent_val > 0.1 else ("BEARISH" if news_sent_val < -0.1 else "NEUTRAL")

        r = rows_by_ticker.get(ticker, {})
        if st_sent is not None and news_sig is not None and st_sent != news_sig:
            divergences.append({
                "Ticker":       ticker,
                "Company":      r.get("company", ticker),
                "StockTwits":   st_sent,
                "News Sent.":   news_sig,
                "News Score":   f"{int(round(news_sent_val*100)):+d}" if news_sent_val is not None else "—",
                "Price Chg":    r.get("chg", "—"),
                "Comp. Signal": r.get("signal", "—"),
            })

    if not divergences:
        st.markdown(
            '<div class="sparse-note">No StockTwits vs News divergences detected right now — '
            'or signals are too sparse. Divergences will appear as daily data accumulates '
            '(target: 30+ days, July 2026).</div>',
            unsafe_allow_html=True,
        )
        return

    div_df = pd.DataFrame(divergences)

    def _color_sig(val):
        if val == "BULLISH":
            return f"color: {GREEN}; font-weight: 600"
        if val == "BEARISH":
            return f"color: {RED}; font-weight: 600"
        return f"color: {MUTED}"

    st.markdown(f'<div class="sec-label">{len(divergences)} Tickers with StockTwits vs News Signal Divergence</div>',
                unsafe_allow_html=True)

    tbl_html = '<div class="data-tbl-wrap"><table class="data-tbl"><thead><tr>'
    for col in div_df.columns:
        tbl_html += f'<th class="data-tbl-th">{col}</th>'
    tbl_html += '</tr></thead><tbody>'
    for i, row_d in div_df.iterrows():
        cls = "even" if i % 2 == 0 else "odd"
        tbl_html += f'<tr class="{cls}">'
        for col, val in row_d.items():
            color_style = ""
            if col in ("StockTwits", "News Sent.", "Comp. Signal"):
                if val == "BULLISH":
                    color_style = f'style="color:{GREEN};font-weight:600"'
                elif val == "BEARISH":
                    color_style = f'style="color:{RED};font-weight:600"'
            tbl_html += f'<td class="data-tbl-td num" {color_style}>{val}</td>'
        tbl_html += '</tr>'
    tbl_html += '</tbody></table></div>'
    st.markdown(tbl_html, unsafe_allow_html=True)

    note(
        "Shows tickers where StockTwits community sentiment and news headline sentiment point in opposite "
        "directions — potential divergence signals. High divergence can precede volatility as one side is "
        "eventually proven wrong."
    )


# ── Tab: Rolling Correlation ────────────────────────────────────────────────────
def tab_rolling_correlation():
    tab_intro(
        "Shows whether a signal's link to price is getting stronger or weaker over time. "
        "Instead of one fixed number, this recalculates the correlation every N days so you can "
        "see if a signal that worked six months ago is still working today. "
        "A line trending toward zero means the signal is losing its edge for that stock."
    )
    ticker  = st.selectbox("Select ticker", config.TICKERS, index=0, key="rc_ticker")
    window  = st.slider("Rolling window (days)", min_value=7, max_value=30, value=14, step=1, key="rc_window")

    price_df  = load_prices(ticker)
    trends_df = load_trends(ticker)
    wiki_df   = load_wikipedia(ticker)

    if price_df.empty:
        st.info("No price data available.")
        return

    price_s = price_df["close_price"].dropna().sort_index()
    returns = price_s.pct_change()

    fig = go.Figure()
    added = 0

    def _add_rolling(signal_s, name, color, dash="solid"):
        nonlocal added
        aligned = pd.concat([signal_s, returns], axis=1).dropna()
        if len(aligned) < window + 2:
            return
        sig_col = aligned.columns[0]
        ret_col = aligned.columns[1]
        rolled  = aligned[sig_col].rolling(window).corr(aligned[ret_col])
        if rolled.dropna().empty:
            return
        fig.add_trace(go.Scatter(
            x=rolled.index, y=rolled,
            name=name, mode="lines",
            line=dict(color=color, width=2.2, dash=dash),
            hovertemplate=f"{name}: %{{y:.3f}}<extra></extra>",
        ))
        added += 1

    if not trends_df.empty and "interest" in trends_df.columns:
        _add_rolling(trends_df["interest"], "Google Trends", C2)

    if not wiki_df.empty and "page_views" in wiki_df.columns:
        _add_rolling(np.log1p(wiki_df["page_views"]).rename("wiki_log"), "Wikipedia Views", C5, "dash")

    st_df = load_stocktwits(ticker)
    if not st_df.empty and "net_sentiment" in st_df.columns:
        _add_rolling(st_df["net_sentiment"], "StockTwits Sent.", GREEN, "dot")

    news_df = load_news(ticker)
    if not news_df.empty and "avg_sentiment" in news_df.columns:
        _add_rolling(news_df["avg_sentiment"], "News Sentiment", C4, "dashdot")

    if added == 0:
        st.info(f"Not enough overlapping data for {ticker} with a {window}-day window.")
        return

    fig.add_hline(y=0, line_color=BORDER, line_width=1)
    layout = chart_layout(
        f"{ticker}  ·  {window}-Day Rolling Correlation: Each Signal vs Daily Price Return",
        height=360,
    )
    layout["yaxis"].update(
        range=[-1.1, 1.1], zeroline=True, zerolinecolor=BORDER, zerolinewidth=1.5,
        title=dict(text="Pearson r", font=dict(size=10, color=MUTED)),
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    note(
        f"Each line shows the rolling {window}-day Pearson correlation between that signal and same-day price returns. "
        "When a line is consistently positive, the signal moves with price; consistently negative means it moves against. "
        "Stability over time suggests a reliable relationship. Signals with only a few days of data won't appear until sufficient history accumulates."
    )


# ── Tab: Returns Distribution ───────────────────────────────────────────────────
def tab_returns_distribution():
    tab_intro(
        "Compares what happened to stock prices 7 days after a BULLISH, NEUTRAL, or BEARISH signal — "
        "across all 50 tracked stocks. If the signals are working, the green (BULLISH) curve should "
        "sit to the right of the red (BEARISH) curve, meaning bullish calls tended to be followed "
        "by higher returns. The wider the separation, the more meaningful the signal."
    )
    _FWD = 7

    all_bull, all_bear, all_neut = [], [], []

    for ticker in config.TICKERS:
        df = build_historical_signals(ticker)
        if df.empty or len(df) < _FWD + 3:
            continue
        price  = df["close"]
        fwd    = (price.shift(-_FWD) / price - 1) * 100
        for sig, bucket in [("BULLISH", all_bull), ("BEARISH", all_bear), ("NEUTRAL", all_neut)]:
            mask = df["signal"] == sig
            vals = fwd[mask].dropna().tolist()
            bucket.extend(vals)

    if not all_bull and not all_bear and not all_neut:
        st.info("Not enough historical data yet. Check back after 30+ days.")
        return

    fig = go.Figure()
    for vals, name, color in [
        (all_bull, "BULLISH Signal", GREEN),
        (all_bear, "BEARISH Signal", RED),
        (all_neut, "NEUTRAL Signal", MUTED),
    ]:
        if not vals:
            continue
        arr = np.array(vals)
        fig.add_trace(go.Histogram(
            x=arr, name=f"{name} (n={len(arr)})",
            nbinsx=40, opacity=0.65,
            marker_color=color,
            hovertemplate="Return: %{x:.1f}%<br>Count: %{y}<extra></extra>",
        ))

    fig.add_vline(x=0, line_color=TEXT, line_width=1.5, line_dash="solid")
    layout = chart_layout(
        f"{_FWD}-Day Forward Price Return Distribution  ·  Grouped by Composite Signal at Entry",
        height=380,
    )
    layout["barmode"] = "overlay"
    layout["xaxis"].update(ticksuffix="%",
                           title=dict(text=f"{_FWD}-Day Forward Return", font=dict(size=10, color=MUTED)))
    layout["yaxis"].update(title=dict(text="Count (ticker-days)", font=dict(size=10, color=MUTED)))
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    if all_bull or all_bear:
        m1, m2, m3 = st.columns(3)
        with m1:
            if all_bull:
                st.metric("Avg return after BULLISH",
                          f"{np.mean(all_bull):+.1f}%",
                          f"median {np.median(all_bull):+.1f}%")
        with m2:
            if all_bear:
                st.metric("Avg return after BEARISH",
                          f"{np.mean(all_bear):+.1f}%",
                          f"median {np.median(all_bear):+.1f}%")
        with m3:
            if all_neut:
                st.metric("Avg return after NEUTRAL",
                          f"{np.mean(all_neut):+.1f}%",
                          f"median {np.median(all_neut):+.1f}%")

    note(
        f"Histogram of {_FWD}-day forward price returns across all 50 tickers, split by the composite signal "
        f"on the day of entry. If the model has edge, the BULLISH distribution should skew right of the BEARISH one."
    )


# ── Summary / overview page ────────────────────────────────────────────────────
def show_summary():
    rows            = build_summary()
    rows_by_ticker  = {r["ticker"]: r for r in rows}
    basket          = st.session_state.get("basket", list(config.PINNED_TICKERS))
    basket_view     = st.session_state.get("basket_view", False)
    show_sidebar(rows_by_ticker)
    show_header()

    # Basket view: show only basket tickers. Default view: show all 50.
    if basket_view:
        display_rows   = [rows_by_ticker[t] for t in basket if t in rows_by_ticker]
        sparkline_rows = display_rows
    else:
        display_rows   = rows
        sparkline_rows = [rows_by_ticker[t] for t in config.PINNED_TICKERS if t in rows_by_ticker]

    # Ticker strip (always full universe)
    st.markdown(build_ticker_strip_html(rows), unsafe_allow_html=True)

    # Basket mode banner
    if basket_view:
        st.markdown(
            '<div class="basket-mode-banner">Showing your basket — click <strong>VIEW ALL TICKERS</strong>'
            ' in the sidebar to return to the full overview.</div>',
            unsafe_allow_html=True,
        )

    # Market chips
    st.markdown(build_market_chips_html(display_rows), unsafe_allow_html=True)

    # Signal distribution
    st.plotly_chart(
        build_signal_dist_chart(display_rows),
        use_container_width=True,
        config={"displayModeBar": False, "responsive": True},
    )

    # Sparkline grid
    spark_label = "My Basket" if basket_view else "Featured Tickers"
    st.markdown(f'<div class="sec-label">{spark_label}</div>', unsafe_allow_html=True)
    show_sparkline_grid(sparkline_rows)

    # ── Analysis tabs (below Featured Tickers) ────────────────────────────────
    fg_score, fg_label, fg_components = compute_fear_greed(rows)
    (
        tab_fg, tab_corr_mat, tab_lag, tab_bt,
        tab_acc, tab_sector, tab_div, tab_rc, tab_rd,
    ) = st.tabs([
        "Fear & Greed",
        "Correlation Matrix",
        "Lag Analysis",
        "Backtesting",
        "Signal Accuracy",
        "Sector Heatmap",
        "Divergence Detector",
        "Rolling Correlation",
        "Returns Distribution",
    ])

    with tab_fg:
        _fg_tip = (
            "Score 0–100 built from four signals across all tracked tickers: "
            "Signal Breadth (% BULLISH), Price Momentum (% of tickers up today), "
            "average News Sentiment, and Google Trends interest. "
            "Extreme Fear < 25 · Fear 25–45 · Neutral 45–55 · Greed 55–75 · Extreme Greed > 75."
        )
        st.markdown(
            f'<div class="sec-label">Market Fear &amp; Greed Index'
            f'<span class="chip-tip sec-tip">'
            f'<button class="chip-info-btn" aria-label="About Fear and Greed">ⓘ</button>'
            f'<div class="chip-info-popup">{_fg_tip}</div>'
            f'</span></div>',
            unsafe_allow_html=True,
        )
        fg_col_gauge, fg_col_comp = st.columns([1, 2])
        with fg_col_gauge:
            st.plotly_chart(
                build_fear_greed_gauge(fg_score, fg_label, fg_components),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        with fg_col_comp:
            st.markdown('<div style="margin-top:1.2rem"></div>', unsafe_allow_html=True)
            for comp_name, comp_val in fg_components.items():
                bar_color = GREEN if comp_val > 55 else (RED if comp_val < 45 else MUTED)
                st.markdown(
                    f'<div style="margin-bottom:0.5rem">'
                    f'<div style="font-family:Inter;font-size:0.78rem;color:{MUTED};margin-bottom:2px">'
                    f'{comp_name}: <strong style="color:{TEXT}">{comp_val:.0f}</strong></div>'
                    f'<div style="background:{SURFACE2};border-radius:4px;height:6px;overflow:hidden">'
                    f'<div style="width:{comp_val:.0f}%;height:100%;background:{bar_color};border-radius:4px"></div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                f'<div class="chart-note" style="margin-top:0.75rem">'
                f'Score 0–100 · 0–25 Extreme Fear · 25–45 Fear · 45–55 Neutral · 55–75 Greed · 75–100 Extreme Greed'
                f'</div>',
                unsafe_allow_html=True,
            )

    with tab_corr_mat:
        tab_correlation_matrix()

    with tab_lag:
        tab_lag_analysis()

    with tab_bt:
        tab_backtesting()

    with tab_acc:
        tab_signal_accuracy()

    with tab_sector:
        tab_sector_heatmap(rows)

    with tab_div:
        tab_divergence_detector(rows)

    with tab_rc:
        tab_rolling_correlation()

    with tab_rd:
        tab_returns_distribution()

    # Metric definitions
    show_glossary()

    # ── Signal table with search, sector filter, and watchlist ───────────────
    st.markdown('<div class="sec-label">Market Intelligence Overview</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="tab-desc" style="margin-bottom:0.6rem">'
        'Today\'s alt-data readings for all 50 tracked stocks. Click any column header to sort. '
        'Hover the ⓘ icon on a column name to see what it measures. '
        'Click <strong>VIEW →</strong> on any row to open that stock\'s full signal breakdown.'
        '</div>',
        unsafe_allow_html=True,
    )

    # Search bar + sector filter controls
    ctrl_left, ctrl_right = st.columns([3, 2])
    with ctrl_left:
        st.markdown('<div class="tbl-search-wrap">', unsafe_allow_html=True)
        search_q = st.text_input(
            "Search",
            placeholder="Search ticker or company…",
            label_visibility="collapsed",
            key="summary_search",
        )
        st.markdown('</div>', unsafe_allow_html=True)
    with ctrl_right:
        all_sectors = ["All"] + list(SECTORS.keys())
        sector_selected = st.selectbox(
            "Category",
            all_sectors,
            index=all_sectors.index(st.session_state.get("sector_filter", "All"))
            if st.session_state.get("sector_filter", "All") in all_sectors else 0,
            key="sector_select",
        )
        st.session_state["sector_filter"] = sector_selected

    # Apply search filter
    tbl_rows = display_rows
    if search_q:
        q = search_q.strip().lower()
        tbl_rows = [r for r in tbl_rows if q in r["ticker"].lower() or q in r["company"].lower()]

    # Apply sector filter
    if sector_selected != "All":
        sector_tickers = set(SECTORS.get(sector_selected, []))
        tbl_rows = [r for r in tbl_rows if r["ticker"] in sector_tickers]

    # Pin watchlisted tickers to top
    watchlist = st.session_state.get("watchlist", set())
    if watchlist:
        starred   = [r for r in tbl_rows if r["ticker"] in watchlist]
        unstarred = [r for r in tbl_rows if r["ticker"] not in watchlist]
        tbl_rows  = starred + unstarred

    if not tbl_rows:
        st.info("No tickers match the current filter. Try a different search or sector.")
    else:
        st.markdown(build_table_html(tbl_rows, watchlist=watchlist), unsafe_allow_html=True)

    st.markdown(f"""
    <div class="signal-legend">
      <strong>Signal methodology —</strong>
      StockTwits bullish% &gt; 55% = +1 · &lt; 40% = −1 ·
      News sentiment &gt; +10 = +1 · &lt; −10 = −1 ·
      Google Trends &gt; 10% above 7-day avg = +1 · &gt; 10% below = −1 ·
      Prior-day price change &gt; +0.5% = +1 · &lt; −0.5% = −1 ·
      Score ≥ +2 = <span style="color:{GREEN};font-weight:600">BULLISH</span> ·
      ≤ −2 = <span style="color:{RED};font-weight:600">BEARISH</span> ·
      otherwise <span style="color:{MUTED};font-weight:600">NEUTRAL</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(build_animations_js(), unsafe_allow_html=True)


# ── Detail view ────────────────────────────────────────────────────────────────
def _info_label(title, tip):
    """Return a .sec-label div with an inline ⓘ info button."""
    return (
        f'<div class="sec-label">{title}'
        f'<span class="chip-tip sec-tip">'
        f'<button class="chip-info-btn" aria-label="About {title}">ⓘ</button>'
        f'<div class="chip-info-popup">{tip}</div>'
        f'</span></div>'
    )


def show_detail(ticker):
    rows           = build_summary()
    rows_by_ticker = {r["ticker"]: r for r in rows}
    show_sidebar(rows_by_ticker)
    show_header()

    def _go_back():
        st.query_params.clear()
        st.session_state.pop("ticker", None)

    back_col, _, drop_col = st.columns([1.5, 6, 2])
    with back_col:
        st.button("← Back to overview", on_click=_go_back, key="back_btn")
    with drop_col:
        ticker_idx = config.TICKERS.index(ticker) if ticker in config.TICKERS else 0
        new_ticker = st.selectbox("Switch ticker", config.TICKERS, index=ticker_idx,
                                  label_visibility="collapsed", key="detail_ticker_select")
        if new_ticker != ticker:
            st.query_params["ticker"] = new_ticker
            st.rerun()

    # Date range selector
    st.markdown('<div class="detail-date-wrap">', unsafe_allow_html=True)
    dc_label, dc_from, dc_to, dc_reset = st.columns([1.2, 2, 2, 1])
    with dc_label:
        st.markdown('<span class="detail-date-label">Date range</span>', unsafe_allow_html=True)
    default_from = date.today() - pd.Timedelta(days=90)
    with dc_from:
        date_from = st.date_input("From", value=default_from, key="detail_date_from",
                                  label_visibility="collapsed")
    with dc_to:
        date_to = st.date_input("To", value=date.today(), key="detail_date_to",
                                label_visibility="collapsed")
    with dc_reset:
        if st.button("Reset", key="detail_date_reset"):
            st.session_state["detail_date_from"] = default_from
            st.session_state["detail_date_to"]   = date.today()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")

    price_df  = load_prices(ticker)
    st_df     = load_stocktwits(ticker)
    trends_df = load_trends(ticker)
    news_df   = load_news(ticker)

    price = safe_last(price_df, "close_price")
    price_chg = None
    if not price_df.empty and len(price_df["close_price"].dropna()) >= 2:
        s = price_df["close_price"].dropna()
        price_chg = (s.iloc[-1] - s.iloc[-2]) / s.iloc[-2] * 100

    bullish_pct = None
    if not st_df.empty and {"bullish_count", "message_count"}.issubset(st_df.columns):
        valid = st_df.dropna(subset=["message_count"])
        if len(valid) > 0:
            last = valid.iloc[-1]
            if last["message_count"] > 0:
                bullish_pct = last["bullish_count"] / last["message_count"] * 100

    trends_score = safe_last(trends_df, "interest")
    trends_avg   = float(trends_df["interest"].mean()) if not trends_df.empty else None
    news_sent    = safe_last(news_df, "avg_sentiment")
    signal       = compute_signal(bullish_pct, trends_score, trends_avg, news_sent, price_chg)

    sig_color  = GREEN if signal == "BULLISH" else (RED if signal == "BEARISH" else MUTED)
    sig_prefix = "▲" if signal == "BULLISH" else ("▼" if signal == "BEARISH" else "→")

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Price",
                  f"${price:,.2f}" if price is not None else "—",
                  f"{price_chg:+.2f}%" if price_chg is not None else None)
    with m2:
        st.metric("StockTwits Bullish%", f"{bullish_pct:.0f}%" if bullish_pct is not None else "—")
    with m3:
        st.metric("Google Trends", f"{trends_score:.0f}/100" if trends_score is not None else "—")
    with m4:
        st.metric("News Sentiment", f"{int(round(news_sent*100)):+d}" if news_sent is not None else "—")
    with m5:
        st.markdown(f"""
        <div class="signal-metric">
          <div class="sm-label">Composite Signal</div>
          <div class="sm-value" style="color:{sig_color}">{sig_prefix} {signal}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    _chart_cfg = {
        "displayModeBar": False,
        "doubleClick": "reset",
        "displaylogo": False,
        "responsive": True,
    }

    # All signals overlaid — first
    st.markdown(_info_label(
        "All Signals Overlaid (Normalized 0–100)",
        "All four signals (StockTwits, Trends, Wikipedia, News) normalized to a 0–100 scale and "
        "overlaid with price. Reveals which signals lead or lag price — the core question of this project."
    ), unsafe_allow_html=True)
    fig5 = chart_overlay(ticker, date_from=date_from, date_to=date_to)
    st.plotly_chart(fig5, use_container_width=True, config=_chart_cfg)
    note(
        "All four signals normalized to 0–100 and plotted together to reveal lead/lag relationships. "
        "As data accumulates, this chart will show whether sentiment peaks tend to precede or follow "
        "price movements — the core empirical question of this project."
    )

    st.markdown(_info_label(
        "Price History",
        "Daily closing price from Yahoo Finance. This is the baseline — all alt-data signals are "
        "tested against future price moves to evaluate their predictive value."
    ), unsafe_allow_html=True)
    fig1 = chart_price(ticker, date_from=date_from, date_to=date_to)
    if fig1:
        st.plotly_chart(fig1, use_container_width=True, config=_chart_cfg)
    else:
        st.info("No price data available.")
    note(
        f"Daily closing price for <strong>{ticker}</strong> over the past 90 days, sourced from Yahoo Finance. "
        f"Price is the baseline signal — all sentiment and search signals are compared against subsequent "
        f"price moves to test predictive information."
    )

    st.markdown(_info_label(
        "Price Forecast (1 / 3 / 7 Day)",
        "Model-generated price targets combining the linear price trend with the composite alt-data "
        "signal score. Past prediction markers are colour-coded once outcomes are known: "
        "▲ green = correct direction, ▼ red = incorrect, ○ grey = pending."
    ), unsafe_allow_html=True)
    _render_pred_chart(ticker, load_predictions())

    st.markdown(_info_label(
        "StockTwits Community Sentiment",
        "StockTwits users voluntarily tag posts as Bullish or Bearish — providing direct sentiment "
        "labels. The chart shows % Bullish and % Bearish each day, both normalized to 0–100 alongside price."
    ), unsafe_allow_html=True)
    result2 = chart_stocktwits(ticker, date_from=date_from, date_to=date_to)
    if result2[0] is not None:
        fig2, sparse2 = result2
        st.plotly_chart(fig2, use_container_width=True, config=_chart_cfg)
    else:
        sparse2 = True
        st.info("No StockTwits data yet.")
    if sparse2:
        sparse_note()
    note(
        "StockTwits users voluntarily tag posts as 'Bullish' or 'Bearish' — providing direct labels "
        "rather than inferred tone. Both series and the price line are normalized to 0–100 for visual "
        "comparison of direction and magnitude. Academic research has linked StockTwits sentiment to "
        "next-day abnormal returns for high-attention stocks."
    )

    st.markdown(_info_label(
        "Google Trends Search Interest",
        "Relative search volume for this ticker on Google, scored 0–100. Rising retail search "
        "attention can signal growing interest before it shows up in price."
    ), unsafe_allow_html=True)
    fig3 = chart_trends(ticker, date_from=date_from, date_to=date_to)
    if fig3:
        st.plotly_chart(fig3, use_container_width=True, config=_chart_cfg)
    else:
        st.info("No Google Trends data available.")
    note(
        "Search interest normalized to 0–100 within the 90-day period, alongside normalized price "
        "(dotted). The dotted curve also shows the 7-day rolling average. Da, Engelberg &amp; Gao (2011) "
        "linked retail search attention to short-term price pressure in <em>In Search of Attention</em>."
    )

    st.markdown(_info_label(
        "Wikipedia Page Views",
        "Daily Wikipedia article views, log-scaled and normalized to 0–100. Spikes reflect sudden "
        "public attention — earnings surprises, news events. Research links Wikipedia views to "
        "market moves up to 6 days ahead."
    ), unsafe_allow_html=True)
    fig_wiki = chart_wikipedia(ticker, date_from=date_from, date_to=date_to)
    if fig_wiki is not None:
        st.plotly_chart(fig_wiki, use_container_width=True, config=_chart_cfg)
        note(
            "Daily Wikipedia page-view counts (log-scaled, normalized 0–100) alongside normalized price (dotted). "
            "High page-view spikes reflect sudden public attention — news events, earnings surprises, viral moments. "
            "Moat et al. (2013, <em>Scientific Reports</em>) found Wikipedia views of financial topics "
            "predict market moves up to 6 days ahead for DJIA components."
        )
    else:
        article = config.WIKI_ARTICLES.get(ticker)
        if article is None:
            st.info(f"No Wikipedia article mapped for {ticker} — page-view data unavailable.")
        else:
            st.info("Wikipedia page-view data not yet collected. Run the pipeline to fetch it.")

    st.markdown(_info_label(
        "News Headline Sentiment",
        "VADER sentiment scores for Yahoo Finance headlines, normalized to 0–100. The neutral line "
        "is at raw score 0. Bars above = net-positive news days; below = net-negative days."
    ), unsafe_allow_html=True)
    result4 = chart_news(ticker, date_from=date_from, date_to=date_to)
    if result4[0] is not None:
        fig4, sparse4 = result4
        st.plotly_chart(fig4, use_container_width=True, config=_chart_cfg)
    else:
        sparse4 = True
        st.info("No news data yet.")
    if sparse4:
        sparse_note()
    note(
        "VADER sentiment scores normalized to 0–100 alongside normalized price (dotted). The neutral "
        "reference line shows the position of raw sentiment = 0 on the normalized axis. Bars above "
        "the line are net-positive days; below are net-negative days."
    )

    # Recent headlines
    headlines = fetch_recent_headlines(ticker)
    if headlines:
        st.markdown('<div class="sec-label" style="margin-top:1.2rem">Recent Headlines</div>',
                    unsafe_allow_html=True)
        items_html = ""
        for h in headlines:
            date_str = h["date"].strftime("%-m/%-d") if h["date"] else ""
            source   = f'<span class="hl-source">{h["source"]}</span>' if h["source"] else ""
            title_html = (
                f'<a href="{h["url"]}" target="_blank" rel="noopener" class="hl-link">{h["title"]}</a>'
                if h["url"] else
                f'<span class="hl-title">{h["title"]}</span>'
            )
            items_html += (
                f'<div class="hl-row">'
                f'<span class="hl-date">{date_str}</span>'
                f'<span class="hl-body">{title_html}{source}</span>'
                f'</div>'
            )
        st.markdown(f'<div class="hl-feed">{items_html}</div>', unsafe_allow_html=True)
    st.markdown(build_animations_js(), unsafe_allow_html=True)


# ── About page ─────────────────────────────────────────────────────────────────
def show_about():
    show_sidebar({})
    show_header()

    def _go_home():
        st.query_params.clear()
    st.button("← Back to overview", on_click=_go_home, key="about_back_btn")

    st.markdown("""
    <div class="about-hero">
      <div class="about-hero-eyebrow">Research Dashboard · Public</div>
      <div class="about-hero-title">Alt Data Signal Tracker</div>
      <div class="about-hero-sub">
        A live financial research project tracking five alternative data signals against
        daily stock prices across 50 consumer equities — to test whether public attention
        and retail sentiment lead or lag the market.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Research Question ──────────────────────────────────────────────────────
    st.markdown('<div class="about-section">', unsafe_allow_html=True)
    st.markdown('<div class="about-section-title">The Research Question</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="about-body">
      <p>
        Traditional finance assumes markets are efficient — prices already reflect all
        publicly available information. But retail investors increasingly shape short-term
        price dynamics, especially for high-attention consumer stocks. This project asks:
      </p>
      <p style="font-family:'DM Serif Display',serif;font-size:1.1rem;color:#1C160E;
                border-left:3px solid #8B6F47;padding-left:1rem;margin:1rem 0;">
        Do alternative data signals — retail sentiment, search volume, and public
        attention — systematically lead or lag stock price movements, and by how many days?
      </p>
      <p>
        If sentiment consistently leads prices by 1–2 days, it could carry real
        informational value. If it lags, it reflects traders reacting to moves
        that already happened. The cross-correlation analysis (lags −3 to +3 days)
        is designed to answer this empirically across all 50 tickers once sufficient
        data accumulates — target analysis start: <strong>July 22, 2026</strong> (30+ days of history).
      </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Data Sources ───────────────────────────────────────────────────────────
    st.markdown('<div class="about-section">', unsafe_allow_html=True)
    st.markdown('<div class="about-section-title">Data Sources</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="about-cards">

      <div class="about-card">
        <div class="about-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="2 18 8 10 14 14 22 4"/><polyline points="17 4 22 4 22 9"/></svg></div>
        <div class="about-card-name">Prices</div>
        <div class="about-card-title">Stock Closing Prices</div>
        <div class="about-card-body">
          Daily closing prices from Yahoo Finance via yfinance.
          90 days of history, refreshed every morning.
          Used as the baseline — all signals are compared against
          subsequent price moves to test predictive value.
        </div>
        <div class="about-card-badge">90-day rolling · daily refresh</div>
      </div>

      <div class="about-card">
        <div class="about-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></div>
        <div class="about-card-name">StockTwits</div>
        <div class="about-card-title">Community Sentiment</div>
        <div class="about-card-body">
          Retail investors on StockTwits voluntarily tag each post as
          Bullish or Bearish. The public API returns today's counts.
          Unlike news sentiment (inferred), these are self-labeled
          signals — making them unusually clean for research.
        </div>
        <div class="about-card-badge">accumulates from June 2026</div>
      </div>

      <div class="about-card">
        <div class="about-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><polyline points="7 13 9 10 12 13 15 8"/></svg></div>
        <div class="about-card-name">Google Trends</div>
        <div class="about-card-title">Search Interest</div>
        <div class="about-card-body">
          Google's relative search volume index, normalized 0–100
          within the 90-day window. Captures how much retail attention
          a stock is getting before trading decisions are made.
          Higher interest often precedes volatility.
        </div>
        <div class="about-card-badge">90-day rolling · daily refresh</div>
      </div>

      <div class="about-card">
        <div class="about-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="14" y2="17"/></svg></div>
        <div class="about-card-name">News</div>
        <div class="about-card-title">Headline Sentiment</div>
        <div class="about-card-body">
          Yahoo Finance headlines analyzed with VADER — a sentiment
          tool built for financial and social media text. Each day's
          average sentiment score is stored (−1 to +1 raw, shown as
          −100 to +100 on the dashboard).
        </div>
        <div class="about-card-badge">accumulates from June 2026</div>
      </div>

      <div class="about-card">
        <div class="about-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg></div>
        <div class="about-card-name">Wikipedia</div>
        <div class="about-card-title">Page View Attention</div>
        <div class="about-card-body">
          Daily Wikipedia article views from the free Wikimedia REST
          API (no credentials needed). Views are log-transformed to
          dampen viral spikes, then normalized 0–100. Spikes reflect
          news events, earnings surprises, or sudden public interest.
        </div>
        <div class="about-card-badge">91-day history · daily refresh</div>
      </div>

    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── How Signals Are Calculated ─────────────────────────────────────────────
    st.markdown('<div class="about-section">', unsafe_allow_html=True)
    st.markdown('<div class="about-section-title">How Signals Are Calculated</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="about-body">
      <p>
        <strong>Normalization (0–100).</strong> Every signal is rescaled to a 0–100 range
        within its own history window using min-max normalization. This lets completely
        different data types — search volume, sentiment scores, page views — be plotted
        on the same chart and compared visually. A value of 100 means the highest point
        in the window; 0 means the lowest.
      </p>
      <p>
        <strong>Wikipedia log-transform.</strong> Raw Wikipedia views are first
        log-transformed (log(views + 1)) before normalization. This prevents a single
        viral day from flattening all other variation — a stock might get 1,000 views
        normally and 500,000 views during an earnings report. Without the log transform,
        you'd see one spike and nothing else.
      </p>
      <p>
        <strong>News sentiment scale.</strong> VADER returns scores from −1.0 (most negative)
        to +1.0 (most positive). The dashboard multiplies by 100 and rounds to whole numbers,
        so you see integers like +32 or −17. Zero means neutral.
      </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Composite Signal ───────────────────────────────────────────────────────
    st.markdown('<div class="about-section">', unsafe_allow_html=True)
    st.markdown('<div class="about-section-title">The Composite Signal (BULLISH / NEUTRAL / BEARISH)</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="about-body">
      <p>
        Each ticker gets a composite signal based on a simple majority vote across up to four
        independent indicators. Each indicator casts +1 (bullish), −1 (bearish), or 0 (neutral).
        A total score ≥ +2 → <strong style="color:#3A6B35">BULLISH</strong>,
        ≤ −2 → <strong style="color:#9B3A28">BEARISH</strong>, else <strong>NEUTRAL</strong>.
      </p>
    </div>
    <table class="about-signal-table">
      <thead>
        <tr>
          <th>Signal</th>
          <th>Bullish condition (+1)</th>
          <th>Bearish condition (−1)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>StockTwits Bullish%</strong></td>
          <td class="bull">&gt; 55% bullish posts</td>
          <td class="bear">&lt; 40% bullish posts</td>
        </tr>
        <tr>
          <td><strong>News Sentiment</strong></td>
          <td class="bull">Raw VADER &gt; +0.10</td>
          <td class="bear">Raw VADER &lt; −0.10</td>
        </tr>
        <tr>
          <td><strong>Google Trends</strong></td>
          <td class="bull">&gt; 10% above its own 7-day average</td>
          <td class="bear">&gt; 10% below its own 7-day average</td>
        </tr>
        <tr>
          <td><strong>Price Change</strong></td>
          <td class="bull">Daily return &gt; +0.5%</td>
          <td class="bear">Daily return &lt; −0.5%</td>
        </tr>
      </tbody>
    </table>
    <div class="about-body" style="margin-top:0.75rem">
      <p>
        Wikipedia views are tracked and charted but not yet included in the composite vote —
        the research is still validating whether page-view spikes are directionally
        informative or purely a measure of attention regardless of sentiment.
      </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Lead/Lag Correlation ───────────────────────────────────────────────────
    st.markdown('<div class="about-section">', unsafe_allow_html=True)
    st.markdown('<div class="about-section-title">Lead / Lag Correlation Analysis</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="about-body">
      <p>
        The core analytical output of this project is a cross-correlation matrix computed
        daily. For each signal and each ticker, we measure the Pearson correlation between
        the signal on day <em>t</em> and the stock return on day <em>t + lag</em>, for lags
        from −3 to +3 days.
      </p>
      <p>
        <strong>Positive lag</strong> (e.g., lag = +2): the signal today is correlated with
        the price move two days from now. If this is consistently strong across tickers,
        the signal has predictive power.
      </p>
      <p>
        <strong>Negative lag</strong> (e.g., lag = −2): the price two days ago is correlated
        with today's signal. This means the signal is <em>reacting</em> to past price moves —
        people search more after a stock already moved.
      </p>
      <p>
        <strong>Lag = 0</strong>: contemporaneous correlation — signal and return move together
        on the same day, but neither drives the other.
      </p>
      <p>
        Results are stored in <em>data/correlations_all.csv</em> and updated every pipeline run.
        Meaningful interpretation requires at least 30 days of history. The correlation module
        currently requires ≥ 10 overlapping observations to compute a value; otherwise it reports
        no data for that pair.
      </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── How to Use the Dashboard ───────────────────────────────────────────────
    st.markdown('<div class="about-section">', unsafe_allow_html=True)
    st.markdown('<div class="about-section-title">How to Use the Dashboard</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="about-steps">

      <div class="about-step">
        <div class="about-step-num">1</div>
        <div class="about-step-body">
          <strong>Overview page</strong> — The default view shows all 50 tracked tickers
          in a signal table with live price, daily change, StockTwits bullish%, Google
          Trends score, news sentiment, and composite signal. Above the table, sparkline
          cards show 14-day price mini-charts for pinned or basket tickers.
        </div>
      </div>

      <div class="about-step">
        <div class="about-step-num">2</div>
        <div class="about-step-body">
          <strong>My Basket (sidebar)</strong> — Add any of the 50 tickers to your personal
          basket using the search box on the left. Remove them with the × button.
          Click <em>SEE MY BASKET</em> to filter the entire dashboard — sparklines,
          chips, and table — to only your selected tickers.
        </div>
      </div>

      <div class="about-step">
        <div class="about-step-num">3</div>
        <div class="about-step-body">
          <strong>Detail view</strong> — Click <em>VIEW →</em> next to any ticker in the
          table to open its full detail page. You'll see six sections: all signals overlaid,
          price history, StockTwits sentiment, Google Trends, Wikipedia page views, and news
          sentiment — each with an explanation. Recent news headlines appear below the
          news chart.
        </div>
      </div>

      <div class="about-step">
        <div class="about-step-num">4</div>
        <div class="about-step-body">
          <strong>Switch tickers</strong> — On any detail page, use the dropdown in the top
          right to jump to a different ticker without going back to the overview.
        </div>
      </div>

      <div class="about-step">
        <div class="about-step-num">5</div>
        <div class="about-step-body">
          <strong>Data freshness</strong> — The pipeline runs automatically at 6:30 AM ET
          every day, pushes fresh CSVs to GitHub, and the Streamlit Cloud app refreshes
          within ~60 seconds. StockTwits and news data accumulate one row per day —
          signal analysis will be most meaningful after July 22, 2026.
        </div>
      </div>

    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Tickers Tracked ────────────────────────────────────────────────────────
    st.markdown('<div class="about-section">', unsafe_allow_html=True)
    st.markdown('<div class="about-section-title">Tickers Tracked (50)</div>', unsafe_allow_html=True)
    ticker_rows = []
    for i in range(0, len(config.TICKERS), 5):
        batch = config.TICKERS[i:i+5]
        ticker_rows.append(
            "".join(
                f'<span style="display:inline-block;font-family:JetBrains Mono,monospace;'
                f'font-size:0.75rem;background:var(--surface);border:1px solid var(--border);'
                f'border-radius:4px;padding:0.15rem 0.45rem;margin:0.2rem 0.2rem 0.2rem 0;'
                f'color:var(--accent)">{t}</span>'
                for t in batch
            )
        )
    st.markdown(
        '<div style="margin-top:0.5rem">' + "".join(ticker_rows) + '</div>',
        unsafe_allow_html=True,
    )
    st.markdown("""
    <div class="about-body" style="margin-top:0.75rem">
      <p>
        Sectors covered: mega-cap tech, social media, fintech, EV &amp; auto,
        retail &amp; consumer, defense &amp; space, biotech &amp; pharma,
        quantum computing, and energy. SPCX (Space Exploration ETF) has no
        Wikipedia article; all other tickers have full five-source coverage.
      </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Academic References ────────────────────────────────────────────────────
    st.markdown('<div class="about-section">', unsafe_allow_html=True)
    st.markdown('<div class="about-section-title">Academic References</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="about-ref">
      <div class="ref-title">Twitter Mood Predicts the Stock Market</div>
      <div class="ref-authors">Bollen, J., Mao, H., &amp; Zeng, X. (2011)</div>
      <div class="ref-venue">Journal of Computational Science, 2(1), 1–8</div>
      Found that public mood on Twitter (calm, alert, sure, vital, kind, happy) correlates
      with DJIA movements with 87.6% accuracy when using a specific emotional dimension.
    </div>
    <div class="about-ref">
      <div class="ref-title">StockTwits Sentiment and Abnormal Returns</div>
      <div class="ref-authors">Sprenger, T. O., Tumasjan, A., Sandner, P. G., &amp; Welpe, I. M. (2014)</div>
      <div class="ref-venue">Journal of Business Finance &amp; Accounting, 41(7–8), 791–830</div>
      Directly links StockTwits bullish/bearish sentiment to next-day abnormal returns and
      trading volume — the closest academic precedent for this project's StockTwits signal.
    </div>
    <div class="about-ref">
      <div class="ref-title">In Search of Attention</div>
      <div class="ref-authors">Da, Z., Engelberg, J., &amp; Gao, P. (2011)</div>
      <div class="ref-venue">Journal of Finance, 66(5), 1461–1499</div>
      Showed that Google SVI (Search Volume Index) for stock tickers predicts short-term
      price increases and subsequent reversals — validating the Google Trends signal used here.
    </div>
    <div class="about-ref">
      <div class="ref-title">Quantifying Trading Behavior in Financial Markets Using Google Trends</div>
      <div class="ref-authors">Preis, T., Moat, H. S., &amp; Stanley, H. E. (2013)</div>
      <div class="ref-venue">Scientific Reports, 3, 1684</div>
      Showed that increases in search volume for financially relevant terms preceded
      market downturns, suggesting search data carries directional predictive power.
    </div>
    <div class="about-ref">
      <div class="ref-title">Quantifying the Advantage of Looking Forward</div>
      <div class="ref-authors">Moat, H. S., Curme, C., Avakian, A., Kenett, D. Y., Stanley, H. E., &amp; Preis, T. (2013)</div>
      <div class="ref-venue">Scientific Reports, 3, 2013</div>
      Found that changes in Wikipedia article views for financial topics preceded DJIA movements
      up to 6 days in advance — the primary academic foundation for the Wikipedia page-view signal.
    </div>
    <div class="about-ref">
      <div class="ref-title">Giving Content to Investor Sentiment: The Role of Media in the Stock Market</div>
      <div class="ref-authors">Tetlock, P. C. (2007)</div>
      <div class="ref-venue">Journal of Finance, 62(3), 1139–1168</div>
      Demonstrated that pessimistic language in the Wall Street Journal's "Abreast of the Market"
      column predicts downward pressure on the Dow Jones — foundational work for the
      news sentiment signal.
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Tech Stack ─────────────────────────────────────────────────────────────
    st.markdown('<div class="about-section">', unsafe_allow_html=True)
    st.markdown('<div class="about-section-title">Technical Stack</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="about-body">
      <p>
        <strong>Language:</strong> Python 3.9 on macOS.
        <strong>Dashboard:</strong> Streamlit + Plotly, deployed on Streamlit Cloud (free tier).
        <strong>Data storage:</strong> CSV files in <em>data/</em> — one file per ticker per source
        (currently ~250 files), committed to a public GitHub repository and loaded at runtime.
      </p>
      <p>
        <strong>Pipeline:</strong> <em>run_pipeline.py</em> runs six steps in sequence —
        prices, StockTwits, Google Trends, news, Wikipedia, and lead/lag correlations —
        then pushes the updated CSVs to GitHub automatically. The pipeline is scheduled via
        macOS launchd to run at 6:30 AM ET daily.
      </p>
      <p>
        <strong>Data sources:</strong>
        Yahoo Finance (yfinance), StockTwits public API, Google Trends (pytrends),
        VADER sentiment (run locally at pipeline time — not installed on Streamlit Cloud),
        Wikimedia REST API (free, no credentials).
      </p>
      <p>
        <strong>GitHub:</strong>
        <a href="https://github.com/ellaktran-hub/alt-data-signal-tracker"
           target="_blank" rel="noopener" style="color:var(--accent)">
          ellaktran-hub/alt-data-signal-tracker
        </a>
      </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ── Predictions page ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_predictions():
    p = DATA_DIR / "predictions.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _render_pred_chart(ticker, pred_df):
    """Render price history + forecast chart, metrics row, and note for one ticker."""
    if pred_df.empty:
        st.info("No prediction data yet — run the pipeline to generate predictions.")
        return
    today_preds = pred_df[pred_df["date"] == pred_df["date"].max()]
    ticker_row  = today_preds[today_preds["ticker"] == ticker]
    if ticker_row.empty:
        st.info(f"No forecast available for {ticker} yet.")
        return
    sel_row = ticker_row.iloc[0]

    if "pred_price_1d" not in sel_row.index or not pd.notna(sel_row.get("pred_price_1d")):
        st.info("Price forecasts not yet computed — re-run the pipeline to add price predictions.")
        return

    price_df = load_prices(ticker)
    if price_df.empty:
        return

    hist_s        = price_df["close_price"].dropna().sort_index()
    last_date     = hist_s.index[-1]
    current_price = float(hist_s.iloc[-1])
    vol           = float(sel_row.get("vol") or 0.015)

    pred_dates  = [last_date + pd.offsets.BDay(n) for n in [1, 3, 7]]
    pred_prices = [float(sel_row["pred_price_1d"]),
                   float(sel_row["pred_price_3d"]),
                   float(sel_row["pred_price_7d"])]
    pred_ci     = [vol * (n ** 0.5) * current_price for n in [1, 3, 7]]

    sig        = sel_row["signal"]
    cone_color = C1 if sig == "BULLISH" else (RED if sig == "BEARISH" else C4)
    upper      = [p + ci for p, ci in zip(pred_prices, pred_ci)]
    lower      = [p - ci for p, ci in zip(pred_prices, pred_ci)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist_s.index.tolist(), y=hist_s.tolist(),
        mode="lines", name="Price History",
        line=dict(color=C2, width=2.5),
        hovertemplate="%{x|%b %d}: $%{y:,.2f}<extra>History</extra>",
    ))

    past_tkr = pred_df[(pred_df["ticker"] == ticker) &
                       (pred_df["date"] < pred_df["date"].max())].copy()
    _hz_cfg = [
        (1, "pred_price_1d", "actual_1d", "hit_1d", "1d Pred"),
        (3, "pred_price_3d", "actual_3d", "hit_3d", "3d Pred"),
        (7, "pred_price_7d", "actual_7d", "hit_7d", "7d Pred"),
    ]
    for days, pcol, acol, hcol, lbl in _hz_cfg:
        px_list, py_list, pcolors, psyms, ptexts = [], [], [], [], []
        ax_list, ay_list = [], []
        for _, pr in past_tkr.iterrows():
            pp = pr.get(pcol)
            if not pd.notna(pp):
                continue
            target = pr["date"] + pd.offsets.BDay(days)
            hit    = pr.get(hcol)
            px_list.append(target)
            py_list.append(float(pp))
            ptexts.append(f"Predicted on {pr['date'].strftime('%b %d')}")
            if pd.notna(hit):
                pcolors.append(GREEN if hit else RED)
                psyms.append("triangle-up" if hit else "triangle-down")
            else:
                pcolors.append(MUTED)
                psyms.append("circle-open")
            ap = pr.get(acol)
            if pd.notna(ap):
                ax_list.append(target)
                ay_list.append(float(ap))
        if px_list:
            fig.add_trace(go.Scatter(
                x=px_list, y=py_list, mode="markers", name=lbl,
                marker=dict(color=pcolors, size=9, symbol=psyms),
                customdata=ptexts,
                hovertemplate="%{customdata}<br>Forecast: $%{y:,.2f}<extra>" + lbl + "</extra>",
            ))
        if ax_list:
            fig.add_trace(go.Scatter(
                x=ax_list, y=ay_list, mode="markers", name=f"{lbl} Actual",
                marker=dict(color=TEXT, size=7, symbol="x"),
                hovertemplate="%{x|%b %d} actual: $%{y:,.2f}<extra>" + lbl + " Actual</extra>",
                showlegend=False,
            ))

    fig.add_trace(go.Scatter(
        x=pred_dates + pred_dates[::-1],
        y=upper + lower[::-1],
        fill="toself", fillcolor="rgba(139,111,71,0.12)",
        line=dict(color="rgba(0,0,0,0)"), name="±1σ CI", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=[last_date] + pred_dates, y=[current_price] + pred_prices,
        mode="lines+markers", name=f"Forecast ({sig})",
        line=dict(color=cone_color, width=2, dash="dot"),
        marker=dict(color=cone_color, size=8, symbol="circle"),
        hovertemplate="%{x|%b %d}: $%{y:,.2f}<extra>Forecast</extra>",
    ))

    n_pred_days = pred_df["date"].nunique()
    hist_label  = f"{len(hist_s)}-Day" if len(hist_s) < 90 else "Full"
    fig.update_layout(**chart_layout(
        f"{ticker}  ·  {hist_label} Price History + Forecast"
        + (f"  ·  {n_pred_days} day(s) of predictions" if n_pred_days > 1 else ""),
        height=360,
    ))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.metric("1-Day Forecast", f"${pred_prices[0]:,.2f}",
                  f"{float(sel_row['pred_ret_1d']):+.2f}% vs today")
    with mc2:
        st.metric("3-Day Forecast", f"${pred_prices[1]:,.2f}",
                  f"{float(sel_row['pred_ret_3d']):+.2f}% vs today")
    with mc3:
        st.metric("7-Day Forecast", f"${pred_prices[2]:,.2f}",
                  f"{float(sel_row['pred_ret_7d']):+.2f}% vs today")

    note(
        "Price history shown in full. "
        "Coloured markers = past predictions at their target date: "
        "▲ green = correct direction · ▼ red = wrong direction · ○ grey = outcome pending. "
        "× marks the actual closing price on that date. "
        "Shaded band = ±1σ confidence interval (volatility × √days)."
    )


def show_predictions():
    rows           = build_summary()
    rows_by_ticker = {r["ticker"]: r for r in rows}
    show_sidebar(rows_by_ticker)
    show_header()

    def _go_home():
        st.query_params.clear()
    st.button("← Back to overview", on_click=_go_home, key="pred_back_btn")

    st.markdown("""
    <div class="about-hero">
      <div class="about-hero-eyebrow">Live Research · Daily Updates</div>
      <div class="about-hero-title">Price Predictions</div>
      <div class="about-hero-sub">
        Each day the model forecasts specific dollar prices at 1-day, 3-day, and 7-day
        horizons for all 50 tickers, combining a linear price trend with the composite
        alt-data signal score. As days pass, actual returns are filled in automatically
        and prediction accuracy is tracked.
      </div>
    </div>
    """, unsafe_allow_html=True)

    pred_df = load_predictions()
    if pred_df.empty:
        st.info("No prediction data yet — run the pipeline to generate predictions.")
        return

    today_str = pred_df["date"].max().strftime("%Y-%m-%d")
    today_preds = pred_df[pred_df["date"] == pred_df["date"].max()].copy()
    past_preds  = pred_df[pred_df["date"] < pred_df["date"].max()].copy()

    # ── Forecast Chart ────────────────────────────────────────────────────────
    has_price_cols = "pred_price_1d" in today_preds.columns

    st.markdown(
        '<div class="about-section-title" style="margin-top:1.5rem">Price Forecast Chart</div>',
        unsafe_allow_html=True,
    )

    chart_tickers = sorted(today_preds["ticker"].tolist())
    chart_default = chart_tickers.index("AAPL") if "AAPL" in chart_tickers else 0
    sel_tkr_fc = st.selectbox(
        "Select ticker", chart_tickers, index=chart_default, key="pred_chart_tkr"
    )
    sel_row_fc = today_preds[today_preds["ticker"] == sel_tkr_fc].iloc[0]

    _render_pred_chart(sel_tkr_fc, pred_df)

    # ── Section 1: Today's Forecast ───────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        f'<div class="about-section-title">'
        f'Today\'s Forecast — {today_str}</div>',
        unsafe_allow_html=True,
    )

    # Sort: BEARISH first (most negative score), then NEUTRAL, BULLISH last
    today_preds = today_preds.sort_values("score")

    bullish_n = (today_preds["signal"] == "BULLISH").sum()
    bearish_n = (today_preds["signal"] == "BEARISH").sum()
    neutral_n = (today_preds["signal"] == "NEUTRAL").sum()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Tickers Predicted", len(today_preds))
    with c2:
        st.metric("↑ Predicted UP",   bullish_n)
    with c3:
        st.metric("↓ Predicted DOWN", bearish_n)
    with c4:
        st.metric("→ No Signal",      neutral_n)

    st.markdown('<div style="margin-top:1rem"></div>', unsafe_allow_html=True)

    # Build HTML table for today's predictions
    def _dir_badge(sig):
        if sig == "BULLISH":
            return f'<span style="color:{GREEN};font-weight:700">↑ UP</span>'
        if sig == "BEARISH":
            return f'<span style="color:{RED};font-weight:700">↓ DOWN</span>'
        return f'<span style="color:{MUTED}">→ NEUTRAL</span>'

    def _score_bar(score):
        pct = min(100, max(0, (score + 4) / 8 * 100))
        color = GREEN if score >= 2 else (RED if score <= -2 else MUTED)
        return (
            f'<div style="display:flex;align-items:center;gap:6px">'
            f'<div style="flex:1;height:4px;background:{SURFACE2};border-radius:2px">'
            f'<div style="width:{pct:.0f}%;height:100%;background:{color};border-radius:2px"></div>'
            f'</div>'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:0.78rem;'
            f'color:{color};min-width:20px;text-align:right">{score:+d}</span>'
            f'</div>'
        )

    def _pred_price_cell(val, ret_val):
        if not pd.notna(val):
            return "—"
        color = GREEN if (pd.notna(ret_val) and ret_val > 0) else (RED if (pd.notna(ret_val) and ret_val < 0) else TEXT)
        ret_str = f" ({ret_val:+.1f}%)" if pd.notna(ret_val) else ""
        return (
            f'<span style="font-family:JetBrains Mono,monospace;color:{color}">'
            f'${val:,.2f}{ret_str}</span>'
        )

    tbl_cols = ["TICKER", "COMPANY", "PRICE", "SCORE", "SIGNAL", "1d FORECAST", "3d FORECAST", "TRENDS", "STOCKTWITS", "NEWS"]
    tbl = '<div class="data-tbl-wrap"><table class="data-tbl"><thead><tr>'
    for col in tbl_cols:
        tbl += f'<th class="data-tbl-th">{col}</th>'
    tbl += '</tr></thead><tbody>'

    for i, r in today_preds.iterrows():
        cls    = "even" if i % 2 == 0 else "odd"
        ticker = r["ticker"]
        comp   = config.COMPANIES.get(ticker, ticker)
        trends = f"{r['trends_score']:.0f}" if pd.notna(r.get("trends_score")) else "—"
        st_pct = f"{r['bullish_pct']:.0f}%" if pd.notna(r.get("bullish_pct")) else "—"
        news   = (f"{int(round(r['news_sent']*100)):+d}"
                  if pd.notna(r.get("news_sent")) else "—")
        p1d = _pred_price_cell(r.get("pred_price_1d"), r.get("pred_ret_1d")) if has_price_cols else "—"
        p3d = _pred_price_cell(r.get("pred_price_3d"), r.get("pred_ret_3d")) if has_price_cols else "—"
        tbl += (
            f'<tr class="{cls}">'
            f'<td class="data-tbl-td tkr">{ticker}</td>'
            f'<td class="data-tbl-td left">{comp}</td>'
            f'<td class="data-tbl-td num">${float(r["price"]):,.2f}</td>'
            f'<td class="data-tbl-td">{_score_bar(int(r["score"]))}</td>'
            f'<td class="data-tbl-td num">{_dir_badge(r["signal"])}</td>'
            f'<td class="data-tbl-td num">{p1d}</td>'
            f'<td class="data-tbl-td num">{p3d}</td>'
            f'<td class="data-tbl-td num">{trends}</td>'
            f'<td class="data-tbl-td num">{st_pct}</td>'
            f'<td class="data-tbl-td num">{news}</td>'
            f'</tr>'
        )
    tbl += '</tbody></table></div>'
    st.markdown(tbl, unsafe_allow_html=True)

    note(
        "Score ranges from −4 (all signals bearish) to +4 (all signals bullish). "
        "≥ +2 = UP · ≤ −2 = DOWN · −1 to +1 = NEUTRAL. "
        "Price forecasts show the model's predicted closing price at each horizon (% change from today). "
        "Actual returns will be filled in automatically each morning as prices come in."
    )

    # ── Section 2: Accuracy Scorecard ────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div class="about-section-title">Prediction Accuracy Scorecard</div>',
        unsafe_allow_html=True,
    )

    directional = pred_df[pred_df["signal"].isin(["BULLISH", "BEARISH"])].copy()

    def _accuracy(col_hit):
        vals = directional[col_hit].dropna()
        if len(vals) < 3:
            return None, len(vals)
        return float(vals.mean() * 100), len(vals)

    acc_1d, n_1d = _accuracy("hit_1d")
    acc_3d, n_3d = _accuracy("hit_3d")
    acc_7d, n_7d = _accuracy("hit_7d")

    if acc_1d is None and acc_3d is None and acc_7d is None:
        st.markdown(
            '<div class="sparse-note">Accuracy data is building up — check back tomorrow. '
            'The pipeline fills in actual returns each morning: 1-day results appear after 1 day, '
            '3-day after 3 days, 7-day after 7 days.</div>',
            unsafe_allow_html=True,
        )
    else:
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            if acc_1d is not None:
                delta = f"{acc_1d - 50:+.1f}% vs random"
                st.metric("1-Day Accuracy", f"{acc_1d:.1f}%", delta)
            else:
                st.metric("1-Day Accuracy", f"— ({n_1d} evaluated)")
        with a2:
            if acc_3d is not None:
                delta = f"{acc_3d - 50:+.1f}% vs random"
                st.metric("3-Day Accuracy", f"{acc_3d:.1f}%", delta)
            else:
                st.metric("3-Day Accuracy", f"— ({n_3d} evaluated)")
        with a3:
            if acc_7d is not None:
                delta = f"{acc_7d - 50:+.1f}% vs random"
                st.metric("7-Day Accuracy", f"{acc_7d:.1f}%", delta)
            else:
                st.metric("7-Day Accuracy", f"— ({n_7d} evaluated)")
        with a4:
            total_dir = len(directional)
            total_days = pred_df["date"].nunique()
            st.metric("Days of Predictions", total_days,
                      f"{total_dir} directional calls total")

        # Accuracy over time chart (if enough days)
        dated_acc = (
            directional[directional["hit_1d"].notna()]
            .groupby("date")["hit_1d"]
            .mean()
            .reset_index()
        )
        dated_acc.columns = ["date", "accuracy"]
        if len(dated_acc) >= 3:
            dated_acc["rolling_acc"] = dated_acc["accuracy"].rolling(7, min_periods=1).mean()
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dated_acc["date"], y=dated_acc["accuracy"] * 100,
                name="Daily 1d Accuracy", mode="markers",
                marker=dict(color=C4, size=5),
                hovertemplate="%{y:.1f}%<extra>Daily accuracy</extra>",
            ))
            fig.add_trace(go.Scatter(
                x=dated_acc["date"], y=dated_acc["rolling_acc"] * 100,
                name="7-Day Rolling", mode="lines",
                line=dict(color=C1, width=2.5),
                hovertemplate="%{y:.1f}%<extra>7-Day rolling</extra>",
            ))
            fig.add_hline(y=50, line_color=BORDER, line_dash="dash", line_width=1,
                          annotation_text="random (50%)", annotation_font=dict(size=9, color=MUTED))
            layout = chart_layout("1-Day Prediction Accuracy Over Time", height=280)
            layout["yaxis"].update(range=[0, 105], ticksuffix="%")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Accuracy by signal strength
        if len(directional[directional["hit_1d"].notna()]) >= 5:
            by_score = (
                directional[directional["hit_1d"].notna()]
                .groupby("score")["hit_1d"]
                .agg(["mean", "count"])
                .reset_index()
            )
            by_score.columns = ["score", "accuracy", "count"]
            by_score = by_score[by_score["count"] >= 2]
            if not by_score.empty:
                fig2 = go.Figure()
                colors = [GREEN if s >= 2 else (RED if s <= -2 else MUTED) for s in by_score["score"]]
                fig2.add_trace(go.Bar(
                    x=by_score["score"].tolist(),
                    y=(by_score["accuracy"] * 100).tolist(),
                    marker_color=colors, marker_opacity=0.85,
                    text=[f"{v:.0f}% (n={n})" for v, n in zip(by_score["accuracy"]*100, by_score["count"])],
                    textposition="outside",
                    hovertemplate="Score %{x}: %{y:.1f}%<extra></extra>",
                ))
                fig2.add_hline(y=50, line_color=BORDER, line_dash="dash", line_width=1)
                layout2 = chart_layout("1-Day Accuracy by Signal Strength (score)", height=280)
                layout2["xaxis"].update(
                    tickvals=list(range(-4, 5)),
                    title=dict(text="Score (−4 = strongest bearish, +4 = strongest bullish)",
                               font=dict(size=10, color=MUTED)),
                )
                layout2["yaxis"].update(range=[0, 115], ticksuffix="%")
                fig2.update_layout(**layout2)
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # ── Section 3: Prediction History ─────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div class="about-section-title">Full Prediction History</div>',
        unsafe_allow_html=True,
    )

    if past_preds.empty:
        st.markdown(
            '<div class="sparse-note">No past predictions yet — today is Day 1. '
            'Check back tomorrow to see yesterday\'s predictions alongside actual returns.</div>',
            unsafe_allow_html=True,
        )
    else:
        # Filters
        f1, f2, f3 = st.columns([2, 2, 2])
        with f1:
            sig_filter = st.multiselect(
                "Filter by signal", ["BULLISH", "BEARISH", "NEUTRAL"],
                default=["BULLISH", "BEARISH", "NEUTRAL"], key="pred_sig_filter",
            )
        with f2:
            horizon_view = st.selectbox(
                "Show returns at", ["1 day", "3 days", "7 days"], key="pred_horizon",
            )
        with f3:
            ticker_filter = st.selectbox(
                "Filter by ticker", ["All"] + sorted(past_preds["ticker"].unique().tolist()),
                key="pred_ticker_filter",
            )

        col_ret  = {"1 day": "actual_1d",   "3 days": "actual_3d",   "7 days": "actual_7d"}[horizon_view]
        col_hit  = {"1 day": "hit_1d",      "3 days": "hit_3d",      "7 days": "hit_7d"}[horizon_view]
        col_pred = {"1 day": "pred_price_1d","3 days": "pred_price_3d","7 days": "pred_price_7d"}[horizon_view]

        view = past_preds[past_preds["signal"].isin(sig_filter)].copy()
        if ticker_filter != "All":
            view = view[view["ticker"] == ticker_filter]
        view = view.sort_values("date", ascending=False)

        has_hist_pred_col = col_pred in view.columns

        def _ret_cell(val):
            if pd.isna(val):
                return f'<span style="color:{MUTED}">—</span>'
            color = GREEN if val > 0 else RED
            arrow = "▲" if val > 0 else "▼"
            return f'<span style="color:{color};font-family:JetBrains Mono,monospace">{arrow} {abs(val):.2f}%</span>'

        def _hit_cell(val, sig):
            if sig == "NEUTRAL" or pd.isna(val):
                return "—"
            return f'<span style="color:{GREEN}">✓</span>' if val else f'<span style="color:{RED}">✗</span>'

        def _pred_vs_actual_cell(pred_price, base_price, actual_ret):
            if not has_hist_pred_col or not pd.notna(pred_price):
                return "—"
            # If actual is available, show predicted price + error
            if pd.notna(actual_ret) and pd.notna(base_price):
                actual_price = float(base_price) * (1 + float(actual_ret) / 100)
                err_pct = (float(pred_price) - actual_price) / actual_price * 100
                err_color = MUTED
                return (
                    f'<span style="font-family:JetBrains Mono,monospace">'
                    f'${float(pred_price):,.2f} '
                    f'<span style="color:{err_color};font-size:0.78rem">({err_pct:+.1f}% err)</span>'
                    f'</span>'
                )
            return f'<span style="font-family:JetBrains Mono,monospace">${float(pred_price):,.2f}</span>'

        hist_headers = ["DATE", "TICKER", "SIGNAL", "SCORE", "PRICE AT PRED",
                        f"PREDICTED ({horizon_view.upper()})",
                        f"ACTUAL ({horizon_view.upper()})", "CORRECT"]
        hist_tbl = '<div class="data-tbl-wrap"><table class="data-tbl"><thead><tr>'
        for h in hist_headers:
            hist_tbl += f'<th class="data-tbl-th">{h}</th>'
        hist_tbl += '</tr></thead><tbody>'

        for i, (_, r) in enumerate(view.iterrows()):
            cls  = "even" if i % 2 == 0 else "odd"
            sig  = r["signal"]
            sig_color = GREEN if sig == "BULLISH" else (RED if sig == "BEARISH" else MUTED)
            hist_tbl += (
                f'<tr class="{cls}">'
                f'<td class="data-tbl-td num" style="font-family:JetBrains Mono,monospace">'
                f'{pd.Timestamp(r["date"]).strftime("%b %d")}</td>'
                f'<td class="data-tbl-td tkr">{r["ticker"]}</td>'
                f'<td class="data-tbl-td num" style="color:{sig_color};font-weight:600">{sig}</td>'
                f'<td class="data-tbl-td num" style="font-family:JetBrains Mono,monospace">'
                f'{int(r["score"]):+d}</td>'
                f'<td class="data-tbl-td num">${float(r["price"]):,.2f}</td>'
                f'<td class="data-tbl-td num">{_pred_vs_actual_cell(r.get(col_pred), r.get("price"), r.get(col_ret))}</td>'
                f'<td class="data-tbl-td num">{_ret_cell(r.get(col_ret))}</td>'
                f'<td class="data-tbl-td num">{_hit_cell(r.get(col_hit), sig)}</td>'
                f'</tr>'
            )
        hist_tbl += '</tbody></table></div>'
        st.markdown(hist_tbl, unsafe_allow_html=True)

        note(
            "Returns are calculated from the closing price on the prediction date to the closing price "
            f"{horizon_view} later. Predicted price is the model's forecast; error % shows how far off it was. "
            "✓ = prediction was correct direction. NEUTRAL predictions have no ✓/✗."
        )

    # ── Section 4: Per-Ticker Track Record ────────────────────────────────────
    if not past_preds.empty:
        st.markdown("---")
        st.markdown(
            '<div class="about-section-title">Per-Ticker Track Record</div>',
            unsafe_allow_html=True,
        )
        ticker_opts = sorted(past_preds["ticker"].unique().tolist())
        sel_ticker  = st.selectbox("Select ticker", ticker_opts, key="pred_tkr_detail")
        tkr_df      = past_preds[past_preds["ticker"] == sel_ticker].copy()

        # Mini accuracy stats
        dir_tkr = tkr_df[tkr_df["signal"].isin(["BULLISH", "BEARISH"])]
        t1, t2, t3, t4 = st.columns(4)
        with t1:
            vals = dir_tkr["hit_1d"].dropna()
            st.metric("1d Accuracy", f"{vals.mean()*100:.0f}%" if len(vals) >= 1 else "—",
                      f"n={len(vals)}")
        with t2:
            vals = dir_tkr["hit_3d"].dropna()
            st.metric("3d Accuracy", f"{vals.mean()*100:.0f}%" if len(vals) >= 1 else "—",
                      f"n={len(vals)}")
        with t3:
            vals = dir_tkr["hit_7d"].dropna()
            st.metric("7d Accuracy", f"{vals.mean()*100:.0f}%" if len(vals) >= 1 else "—",
                      f"n={len(vals)}")
        with t4:
            bull_n = (dir_tkr["signal"] == "BULLISH").sum()
            bear_n = (dir_tkr["signal"] == "BEARISH").sum()
            st.metric("Calls Made", len(dir_tkr), f"{bull_n}↑  {bear_n}↓")

        # Mini chart: 1d actual returns over time for this ticker
        has_ret = tkr_df[tkr_df["actual_1d"].notna()]
        if not has_ret.empty:
            fig_tkr = go.Figure()
            colors_tkr = [GREEN if r > 0 else RED for r in has_ret["actual_1d"]]
            fig_tkr.add_trace(go.Bar(
                x=has_ret["date"].tolist(),
                y=has_ret["actual_1d"].tolist(),
                marker_color=colors_tkr,
                marker_opacity=0.8,
                text=[
                    (f'<span style="color:{GREEN}">✓</span>'
                     if h else f'<span style="color:{RED}">✗</span>')
                    if s in ("BULLISH", "BEARISH") and pd.notna(h) else ""
                    for s, h in zip(has_ret["signal"], has_ret["hit_1d"])
                ],
                textposition="outside",
                hovertemplate="Date: %{x}<br>1d Return: %{y:.2f}%<extra></extra>",
            ))
            fig_tkr.add_hline(y=0, line_color=BORDER, line_width=1)
            layout_tkr = chart_layout(
                f"{sel_ticker}  ·  Actual 1-Day Return at Each Prediction Date", height=240
            )
            layout_tkr["yaxis"].update(ticksuffix="%")
            fig_tkr.update_layout(**layout_tkr)
            st.plotly_chart(fig_tkr, use_container_width=True, config={"displayModeBar": False})


# ── Routing ────────────────────────────────────────────────────────────────────
def has_any_data():
    return DATA_DIR.exists() and any(DATA_DIR.glob("prices_*.csv"))

# Handle watchlist star toggle via ?star=TICKER
_star_param = st.query_params.get("star", None)
if _star_param:
    _wl = load_watchlist()
    if _star_param in _wl:
        _wl.remove(_star_param)
    else:
        _wl.add(_star_param)
    save_watchlist(_wl)
    st.session_state["watchlist"] = _wl
    st.query_params.clear()
    st.rerun()

_ticker_param = st.query_params.get("ticker", None)
_page_param   = st.query_params.get("page", None)

if _page_param == "about":
    _view = "about"
elif _page_param == "predictions":
    _view = "predictions"
elif _ticker_param:
    _view = "detail"
else:
    _view = "summary"

try:
    if _view == "about":
        show_about()
    elif _view == "predictions":
        show_predictions()
    elif not has_any_data():
        show_header()
        st.markdown(f"""
        <div class="pipeline-offline">
          <div class="po-label">Pipeline Status</div>
          <div class="po-title">Awaiting first pipeline run</div>
          <div class="po-body">
            The automated pipeline runs daily at 06:30 and pushes fresh data to GitHub.
            Once data appears, this dashboard will display 90 days of price history,
            Google Trends, StockTwits sentiment, and news scores for all {len(config.TICKERS)} tickers.
          </div>
        </div>
        """, unsafe_allow_html=True)
    elif _view == "detail":
        show_detail(_ticker_param)
    else:
        show_summary()
except Exception as e:
    st.error(
        f"Dashboard error: `{e}`\n\n"
        "If this is a fresh deployment, data files may still be loading. "
        "Try refreshing in 30 seconds."
    )
    raise
