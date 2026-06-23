"""
dashboard.py
Professional financial research dashboard — Alt Data Signal Tracker.
Run with: python3 -m streamlit run dashboard.py
"""

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

DATA_DIR = Path(__file__).parent / "data"

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


# ── ET timezone helper ─────────────────────────────────────────────────────────
def now_et():
    return datetime.now(ZoneInfo("America/New_York"))

def format_et(dt):
    hour = dt.hour % 12 or 12
    minute = dt.strftime("%M")
    ampm   = "AM" if dt.hour < 12 else "PM"
    return f"{dt.strftime('%b')} {dt.day}, {dt.year} · {hour}:{minute} {ampm} ET"


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

def sparse_note():
    st.markdown(
        '<div class="sparse-note">⚠ Fewer than 3 days collected. '
        'This chart fills in as the daily pipeline runs each morning. '
        'Signals become meaningful after ~30 days of accumulation.</div>',
        unsafe_allow_html=True,
    )

_NORM_SUBTITLE = (
    "<br><sup style='font-style:italic;font-size:9px;color:#7A6A52'>"
    "Price shown as dotted line, normalized to same 0–100 scale for comparison</sup>"
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
        if st.button("ADD TO BASKET", key="basket_add_btn"):
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
            '<div class="sb-about-btn"><a href="?page=about">About this project</a></div>',
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

    ts = format_et(now_et())

    return f"""
<div class="market-chips">
  <div class="chip">
    <div class="chip-label">Tickers Tracked</div>
    <div class="chip-value" data-countup-int="{total}">{total}</div>
  </div>
  <div class="chip">
    <div class="chip-label">Signal Distribution</div>
    <div class="chip-dist">
      <span class="dist-b" data-countup-int="{bullish}">{bullish}</span>
      <span class="dist-sep"> B · </span>
      <span class="dist-r" data-countup-int="{bearish}">{bearish}</span>
      <span class="dist-sep"> Be · </span>
      <span class="dist-n" data-countup-int="{neutral}">{neutral}</span>
      <span class="dist-sep"> N</span>
    </div>
  </div>
  <div class="chip">
    <div class="chip-label">Avg News Sentiment</div>
    <div class="chip-value" data-countup-int="{abs(avg_news_int)}" data-countup-prefix="{avg_sign}">
      {avg_sign}{abs(avg_news_int)}
    </div>
  </div>
  <div class="chip">
    <div class="chip-label">Last Updated</div>
    <div class="chip-value">
      <span class="live-pulse" aria-label="Live data"></span>
      <span class="chip-time">{ts}</span>
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

# col: (label, min-width, centered)
_COLS = [
    ("TICKER",    "70px",  False),
    ("COMPANY",   None,    False),
    ("PRICE",     "80px",  True),
    ("CHG %",     "90px",  True),
    ("BULLISH %", "80px",  True),
    ("TRENDS",    "75px",  True),
    ("NEWS SENT", "90px",  True),
    ("SIGNAL",    "90px",  True),
    ("",          "70px",  True),
]

def build_table_html(rows):
    # Header — inline min-width on each th
    def _th_cell(label, min_w, ctr):
        style = f'style="min-width:{min_w}"' if min_w else ""
        cls   = "data-tbl-th ctr" if ctr else "data-tbl-th"
        if label in _TOOLTIPS:
            return (
                f'<th class="{cls}" {style}>{label}'
                f'<span class="th-tip" tabindex="0">'
                f'<span class="th-tip-icon" aria-label="Definition for {label}">ⓘ</span>'
                f'<span class="th-tip-box" role="tooltip">{_TOOLTIPS[label]}</span>'
                f'</span></th>'
            )
        return f'<th class="{cls}" {style}>{label}</th>'

    head_cells = "".join(_th_cell(label, min_w, ctr) for label, min_w, ctr in _COLS)
    head = f"<thead><tr>{head_cells}</tr></thead>"

    body = "<tbody>"
    for i, r in enumerate(rows):
        row_cls  = "even" if i % 2 == 0 else "odd"
        delay_ms = 800 + i * 80
        ticker   = r["ticker"]
        body += (
            f'<tr class="{row_cls}" style="animation-delay:{delay_ms}ms">'
            f'<td class="data-tbl-td tkr">{ticker}</td>'
            f'<td class="data-tbl-td left">{r["company"]}</td>'
            f'<td class="data-tbl-td num">{r["price"]}</td>'
            f'<td class="data-tbl-td num" style="color:{r["chg_color"]}">{r["chg"]}</td>'
            f'<td class="data-tbl-td num">{r["bullish_pct"]}</td>'
            f'<td class="data-tbl-td num">{r["trends"]}</td>'
            f'<td class="data-tbl-td num">{r["news_sent"]}</td>'
            f'<td class="data-tbl-td num" style="color:{r["sig_color"]};font-weight:600">{r["signal"]}</td>'
            f'<td class="data-tbl-td num"><a href="?ticker={ticker}" class="tbl-detail-btn">VIEW →</a></td>'
            f'</tr>'
        )
    body += "</tbody>"

    return (
        f'<div class="data-tbl-wrap">'
        f'<table class="data-tbl">{head}{body}</table>'
        f'</div>'
    )


# ── Count-up JS ────────────────────────────────────────────────────────────────
def build_animations_js():
    return """
<script>
(function () {
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduced) return;

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
})();
</script>
"""


# ── Chart builders ─────────────────────────────────────────────────────────────
def chart_price(ticker):
    df = load_prices(ticker)
    if df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["close_price"], mode="lines",
        line=dict(color=C1, width=2.5),
        fill="tozeroy", fillcolor="rgba(107,66,38,0.07)",
        name="Close", hovertemplate="$%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(**chart_layout(f"{ticker}  ·  Daily Close Price (USD)"))
    fig.update_yaxes(tickprefix="$")
    return fig


def chart_stocktwits(ticker):
    df = load_stocktwits(ticker)
    if df.empty or "bullish_count" not in df.columns:
        return None, True
    df = df.copy()
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
            line=dict(color="#2C2416", width=1.5, dash="dot"),
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


def chart_trends(ticker):
    df = load_trends(ticker)
    if df.empty:
        return None

    interest_n = norm_0_100(df["interest"])
    fig = go.Figure()
    pn = _price_norm(ticker)
    if pn is not None:
        fig.add_trace(go.Scatter(
            x=pn.index, y=pn, mode="lines",
            line=dict(color="#2C2416", width=1.5, dash="dot"),
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


def chart_news(ticker):
    df = load_news(ticker)
    if df.empty or "avg_sentiment" not in df.columns:
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
            line=dict(color="#2C2416", width=1.5, dash="dot"),
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


def chart_wikipedia(ticker):
    wiki_df  = load_wikipedia(ticker)
    price_df = load_prices(ticker)
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
                line=dict(color=C3, width=1.5, dash="dot"),
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


def chart_overlay(ticker):
    price_df  = load_prices(ticker)
    trends_df = load_trends(ticker)
    st_df     = load_stocktwits(ticker)
    news_df   = load_news(ticker)
    wiki_df   = load_wikipedia(ticker)
    fig       = go.Figure()

    if not price_df.empty:
        p = price_df["close_price"].dropna()
        if len(p) >= 2:
            pn = norm_0_100(p)
            fig.add_trace(go.Scatter(
                x=pn.index, y=pn, mode="lines",
                name="Price (norm)", line=dict(color=C3, width=1.5, dash="dot"),
                hovertemplate="%{y:.1f}<extra>Price</extra>",
            ))
    if not trends_df.empty:
        n = norm_0_100(trends_df["interest"])
        fig.add_trace(go.Scatter(
            x=n.index, y=n, mode="lines", name="Trends",
            line=dict(color=C2, width=2.5),
            hovertemplate="%{y:.1f}<extra>Trends</extra>",
        ))
    if not st_df.empty and "net_sentiment" in st_df.columns:
        n = norm_0_100(st_df["net_sentiment"])
        fig.add_trace(go.Scatter(
            x=n.index, y=n, mode="lines+markers", name="StockTwits",
            line=dict(color=GREEN, width=2.5), marker=dict(size=6),
            hovertemplate="%{y:.1f}<extra>StockTwits</extra>",
        ))
    if not news_df.empty and "avg_sentiment" in news_df.columns:
        n = norm_0_100(news_df["avg_sentiment"])
        fig.add_trace(go.Scatter(
            x=n.index, y=n, mode="lines+markers", name="News",
            line=dict(color=C4, width=2.5), marker=dict(size=6),
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
    st.markdown("""
    <button class="hamburger-btn" id="hamburger-btn" aria-label="Open menu">
      <span></span><span></span><span></span>
    </button>
    <div class="sidebar-overlay" id="sidebar-overlay"></div>
    """, unsafe_allow_html=True)
    components.html("""<script>
    (function(){
      var pd=window.parent.document;
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
    })();
    </script>""", height=0)
    st.markdown(f"""
    <div class="rh">
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
    </div>
    """, unsafe_allow_html=True)


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
        display_rows  = [rows_by_ticker[t] for t in basket if t in rows_by_ticker]
        sparkline_rows = display_rows
    else:
        display_rows  = rows
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

    # Sparkline grid — pinned 4 in default view, full basket in basket view
    spark_label = "My Basket" if basket_view else "Featured Tickers"
    st.markdown(f'<div class="sec-label">{spark_label}</div>', unsafe_allow_html=True)
    show_sparkline_grid(sparkline_rows)

    # Metric definitions (collapsed by default)
    show_glossary()

    # Signal table
    st.markdown('<div class="sec-label">Market Intelligence Overview</div>', unsafe_allow_html=True)
    st.markdown(build_table_html(display_rows), unsafe_allow_html=True)

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

    # All signals overlaid — first
    st.markdown('<div class="sec-label">All Signals Overlaid (Normalized 0–100)</div>', unsafe_allow_html=True)
    fig5 = chart_overlay(ticker)
    st.plotly_chart(fig5, use_container_width=True, config={"displayModeBar": False, "responsive": True})
    note(
        "All four signals normalized to 0–100 and plotted together to reveal lead/lag relationships. "
        "As data accumulates, this chart will show whether sentiment peaks tend to precede or follow "
        "price movements — the core empirical question of this project."
    )

    st.markdown('<div class="sec-label">Price History</div>', unsafe_allow_html=True)
    fig1 = chart_price(ticker)
    if fig1:
        st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False, "responsive": True})
    else:
        st.info("No price data available.")
    note(
        f"Daily closing price for <strong>{ticker}</strong> over the past 90 days, sourced from Yahoo Finance. "
        f"Price is the baseline signal — all sentiment and search signals are compared against subsequent "
        f"price moves to test predictive information."
    )

    st.markdown('<div class="sec-label">StockTwits Community Sentiment</div>', unsafe_allow_html=True)
    result2 = chart_stocktwits(ticker)
    if result2[0] is not None:
        fig2, sparse2 = result2
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False, "responsive": True})
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

    st.markdown('<div class="sec-label">Google Trends Search Interest</div>', unsafe_allow_html=True)
    fig3 = chart_trends(ticker)
    if fig3:
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False, "responsive": True})
    else:
        st.info("No Google Trends data available.")
    note(
        "Search interest normalized to 0–100 within the 90-day period, alongside normalized price "
        "(dotted). The dotted curve also shows the 7-day rolling average. Da, Engelberg &amp; Gao (2011) "
        "linked retail search attention to short-term price pressure in <em>In Search of Attention</em>."
    )

    st.markdown('<div class="sec-label">Wikipedia Page Views</div>', unsafe_allow_html=True)
    fig_wiki = chart_wikipedia(ticker)
    if fig_wiki is not None:
        st.plotly_chart(fig_wiki, use_container_width=True, config={"displayModeBar": False, "responsive": True})
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

    st.markdown('<div class="sec-label">News Headline Sentiment</div>', unsafe_allow_html=True)
    result4 = chart_news(ticker)
    if result4[0] is not None:
        fig4, sparse4 = result4
        st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False, "responsive": True})
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
        <div class="about-card-icon">📈</div>
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
        <div class="about-card-icon">💬</div>
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
        <div class="about-card-icon">🔍</div>
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
        <div class="about-card-icon">📰</div>
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
        <div class="about-card-icon">📖</div>
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


# ── Routing ────────────────────────────────────────────────────────────────────
def has_any_data():
    return DATA_DIR.exists() and any(DATA_DIR.glob("prices_*.csv"))

_ticker_param = st.query_params.get("ticker", None)
_page_param   = st.query_params.get("page", None)

if _page_param == "about":
    _view = "about"
elif _ticker_param:
    _view = "detail"
else:
    _view = "summary"

try:
    if _view == "about":
        show_about()
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
