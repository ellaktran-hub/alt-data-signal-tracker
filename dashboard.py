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

# ── Session state — basket ─────────────────────────────────────────────────────
if "basket" not in st.session_state:
    st.session_state["basket"] = list(config.TICKERS)
if "basket_user_modified" not in st.session_state:
    st.session_state["basket_user_modified"] = False


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


# ── yfinance live quotes (for non-dataset basket tickers) ──────────────────────
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
            "news_sent":     f"{news_sent:+.3f}" if news_sent is not None else "—",
            "news_sent_raw": news_sent,
            "signal":        signal,
            "sig_color":     sig_color,
        })
    return rows


# ── Sidebar ────────────────────────────────────────────────────────────────────
def show_sidebar(rows_by_ticker):
    with st.sidebar:
        st.markdown('<div class="sb-title">My Basket</div>', unsafe_allow_html=True)

        basket = st.session_state.get("basket", [])

        for ticker in list(basket):
            if ticker in rows_by_ticker:
                r         = rows_by_ticker[ticker]
                price_str = r["price"]
                chg_str   = r["chg"]
                chg_color = r["chg_color"]
                sig_str   = r["signal"]
                sig_color = r["sig_color"]
            else:
                price, chg = fetch_live_quote(ticker)
                price_str  = f"${price:,.2f}" if price is not None else "—"
                if chg is not None:
                    chg_str   = f"▲ {chg:.2f}%" if chg > 0 else f"▼ {abs(chg):.2f}%"
                    chg_color = GREEN if chg > 0 else RED
                else:
                    chg_str, chg_color = "—", MUTED
                sig_str   = "—"
                sig_color = MUTED

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
                    st.session_state["basket_user_modified"] = True
                    st.rerun()

        st.markdown("")
        st.markdown('<div class="sb-add-label">Add ticker</div>', unsafe_allow_html=True)
        new_sym = st.text_input(
            "", placeholder="e.g. GOOG",
            label_visibility="collapsed", key="basket_add_input",
        )
        if st.button("Add to basket", key="basket_add_btn"):
            sym = new_sym.strip().upper()
            if sym and sym not in st.session_state["basket"]:
                valid, _ = validate_ticker_yf(sym)
                if valid:
                    st.session_state["basket"].append(sym)
                    st.session_state["basket_user_modified"] = True
                    st.rerun()
                else:
                    st.error(f"'{sym}' not found — check the ticker symbol.")
            elif sym in st.session_state["basket"]:
                st.warning(f"{sym} is already in your basket.")

        st.markdown("---")

        _SIDEBAR_DEFS = [
            ("price chg %",  "day-over-day price change"),
            ("bullish %",    "share of alt data signals bullish"),
            ("trends",       "google search interest, 0–100"),
            ("news sent",    "news sentiment, −1 to +1"),
            ("signal",       "composite alt data direction"),
        ]
        st.markdown('<div class="sb-defs-header">Definitions</div>', unsafe_allow_html=True)
        for metric, defn in _SIDEBAR_DEFS:
            st.markdown(
                f'<div class="sb-def-row">'
                f'<span class="sb-def-metric">{metric}</span>'
                f'<span class="sb-def-text">{defn}</span>'
                f'</div>',
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

    news_vals = [r["news_sent_raw"] for r in rows if r["news_sent_raw"] is not None]
    avg_news  = sum(news_vals) / len(news_vals) if news_vals else 0.0
    avg_sign  = "+" if avg_news >= 0 else ""
    avg_abs   = abs(avg_news)

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
    <div class="chip-value"
         data-countup-float="{avg_abs:.4f}"
         data-countup-prefix="{avg_sign}"
         data-countup-dec="3">
      {avg_sign}{avg_news:.3f}
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


# ── Basket overlay charts ──────────────────────────────────────────────────────
def show_basket_overlay_charts(basket):
    st.markdown(
        '<div class="sec-label">ALT DATA SIGNALS vs. PRICE</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="overlay-sub">normalized to 0–100 · dotted line = price</div>',
        unsafe_allow_html=True,
    )

    if not basket:
        st.markdown(
            '<div class="overlay-empty">Add tickers to your basket to see overlay charts.</div>',
            unsafe_allow_html=True,
        )
        return

    for i in range(0, len(basket), 2):
        pair = basket[i:i + 2]
        cols = st.columns(len(pair), gap="medium")
        for col, ticker in zip(cols, pair):
            with col:
                st.markdown(
                    f'<div class="overlay-ticker-hdr">{ticker} — {config.COMPANIES.get(ticker, ticker)}</div>',
                    unsafe_allow_html=True,
                )
                fig = chart_overlay(ticker)
                fig.update_layout(height=220, margin=dict(l=40, r=8, t=16, b=30))
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


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
     "aggregate news sentiment scored from −1 (fully bearish coverage) to +1 (fully bullish). "
     "scores near zero mean mixed or neutral reporting. "
     "works best as a confirming signal alongside bullish %."),
    ("signal",
     "the composite signal combining all alt data sources. bullish means the majority of sources "
     "align positive; bearish means majority negative; neutral means mixed or insufficient data "
     "to call a direction. use it as a weight of evidence, not a guarantee."),
]

def show_glossary():
    with st.expander("METRIC DEFINITIONS", expanded=True):
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
        "aggregate news sentiment scored from −1 (fully bearish coverage) to +1 (fully bullish). "
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

# col: (label, width%, centered)
_COLS = [
    ("TICKER",    "10%", False),
    ("COMPANY",   "8%",  False),
    ("PRICE",     "7%",  True),
    ("CHG %",     "13%", True),
    ("BULLISH %", "13%", True),
    ("TRENDS",    "11%", True),
    ("NEWS SENT", "13%", True),
    ("SIGNAL",    "13%", True),
    ("",          "12%", True),
]

def build_table_html(rows):
    colgroup = "<colgroup>" + "".join(
        f'<col style="width:{w}">' for _, w, _ in _COLS
    ) + "</colgroup>"

    head_cells = "".join(_th(label, w, ctr) for label, w, ctr in _COLS)
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
            f'<td class="data-tbl-td act">'
            f'<a href="?ticker={ticker}" class="view-btn">View Details</a>'
            f'</td>'
            f'</tr>'
        )
    body += "</tbody>"

    return (
        f'<div class="data-tbl-wrap">'
        f'<table class="data-tbl">{colgroup}{head}{body}</table>'
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
    pn = _price_norm(ticker)
    if pn is not None:
        fig.add_trace(go.Scatter(
            x=pn.index, y=pn, mode="lines",
            line=dict(color=C3, width=1.5, dash="dot"),
            name="Price (norm)", hovertemplate="%{y:.1f}<extra>Price (norm)</extra>",
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

    pn = _price_norm(ticker)
    if pn is not None:
        fig.add_trace(go.Scatter(
            x=pn.index, y=pn, mode="lines",
            line=dict(color=C3, width=1.5, dash="dot"),
            name="Price (norm)", hovertemplate="%{y:.1f}<extra>Price (norm)</extra>",
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
    fig.add_trace(go.Bar(
        x=sent_n.index, y=sent_n, marker_color=colors,
        name="Sentiment (norm)",
        hovertemplate="%{y:.1f}<extra>Sentiment (norm)</extra>",
    ))
    fig.add_hline(y=neutral_pos, line_color=BORDER, line_width=1,
                  annotation_text="neutral",
                  annotation_font=dict(size=9, color=MUTED),
                  annotation_position="top right")

    pn = _price_norm(ticker)
    if pn is not None:
        fig.add_trace(go.Scatter(
            x=pn.index, y=pn, mode="lines",
            line=dict(color=C3, width=1.5, dash="dot"),
            name="Price (norm)", hovertemplate="%{y:.1f}<extra>Price (norm)</extra>",
        ))

    title = f"{ticker}  ·  News Headline Sentiment (normalized 0–100){_NORM_SUBTITLE}"
    layout = chart_layout(title)
    layout["yaxis"].update(
        range=[0, 105], tickvals=[0, 25, 50, 75, 100],
        title=dict(text="Normalized (0–100)", font=dict(size=9, color=MUTED)),
    )
    fig.update_layout(**layout)
    return fig, sparse


def chart_overlay(ticker):
    price_df  = load_prices(ticker)
    trends_df = load_trends(ticker)
    st_df     = load_stocktwits(ticker)
    news_df   = load_news(ticker)
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
def build_sparkline_grid_html(rows):
    html = '<div class="spark-grid">'
    for i, r in enumerate(rows):
        ticker    = r["ticker"]
        sig_color = r["sig_color"]
        svg       = build_sparkline_svg(ticker, sig_color)
        html += (
            f'<div class="spark-card" '
            f'style="border-top-color:{sig_color};animation-delay:{i * 80}ms">'
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
            f'<div class="spark-btn-wrap">'
            f'<a href="?ticker={ticker}" class="view-btn">View Details</a>'
            f'</div>'
            f'</div>'
        )
    html += '</div>'
    return html


# ── Header ─────────────────────────────────────────────────────────────────────
def show_header():
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
    show_sidebar(rows_by_ticker)
    show_header()

    # Ticker strip
    st.markdown(build_ticker_strip_html(rows), unsafe_allow_html=True)

    # Basket overlay charts
    show_basket_overlay_charts(st.session_state.get("basket", []))

    # Metric definitions (open by default)
    show_glossary()

    # Market chips
    st.markdown(build_market_chips_html(rows), unsafe_allow_html=True)

    # Signal distribution
    st.plotly_chart(
        build_signal_dist_chart(rows),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    # Sparkline grid
    st.markdown('<div class="sec-label">Individual Ticker Signals</div>', unsafe_allow_html=True)
    st.markdown(build_sparkline_grid_html(rows), unsafe_allow_html=True)

    # Signal table
    st.markdown('<div class="sec-label">Market Intelligence Overview</div>', unsafe_allow_html=True)
    st.markdown(build_table_html(rows), unsafe_allow_html=True)

    st.markdown(f"""
    <div class="signal-legend">
      <strong>Signal methodology —</strong>
      StockTwits bullish% &gt; 55% = +1 · &lt; 40% = −1 ·
      News sentiment &gt; +0.10 = +1 · &lt; −0.10 = −1 ·
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

    back_col, _, drop_col = st.columns([1.5, 6, 2])
    with back_col:
        st.markdown('<a href="?" class="back-link">← Back to overview</a>', unsafe_allow_html=True)
    with drop_col:
        new_ticker = st.selectbox("Switch ticker", config.TICKERS, index=config.TICKERS.index(ticker))
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
        st.metric("News Sentiment", f"{news_sent:+.3f}" if news_sent is not None else "—")
    with m5:
        st.markdown(f"""
        <div class="signal-metric">
          <div class="sm-label">Composite Signal</div>
          <div class="sm-value" style="color:{sig_color}">{sig_prefix} {signal}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown('<div class="sec-label">Price History</div>', unsafe_allow_html=True)
    fig1 = chart_price(ticker)
    if fig1:
        st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})
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
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
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
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No Google Trends data available.")
    note(
        "Search interest normalized to 0–100 within the 90-day period, alongside normalized price "
        "(dotted). The dotted curve also shows the 7-day rolling average. Da, Engelberg &amp; Gao (2011) "
        "linked retail search attention to short-term price pressure in <em>In Search of Attention</em>."
    )

    st.markdown('<div class="sec-label">News Headline Sentiment</div>', unsafe_allow_html=True)
    result4 = chart_news(ticker)
    if result4[0] is not None:
        fig4, sparse4 = result4
        st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})
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

    st.markdown('<div class="sec-label">All Signals Overlaid (Normalized 0–100)</div>', unsafe_allow_html=True)
    fig5 = chart_overlay(ticker)
    st.plotly_chart(fig5, use_container_width=True, config={"displayModeBar": False})
    note(
        "All four signals normalized to 0–100 and plotted together to reveal lead/lag relationships. "
        "As data accumulates, this chart will show whether sentiment peaks tend to precede or follow "
        "price movements — the core empirical question of this project."
    )


# ── Routing ────────────────────────────────────────────────────────────────────
def has_any_data():
    return DATA_DIR.exists() and any(DATA_DIR.glob("prices_*.csv"))

_ticker_param = st.query_params.get("ticker", None)
_view = "detail" if (_ticker_param and _ticker_param in config.TICKERS) else "summary"

try:
    if not has_any_data():
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
