"""
dashboard.py
Professional financial research dashboard — Alt Data Signal Tracker.
Run with: python3 -m streamlit run dashboard.py
"""

import sys
from pathlib import Path
from datetime import date, datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
import config

DATA_DIR = Path(__file__).parent / "data"

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Alt Data Signal Tracker",
    page_icon="▲",
    layout="wide",
    initial_sidebar_state="collapsed",
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
    """Return normalized 0-100 price series for a ticker, or None."""
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
            "ticker":       ticker,
            "company":      config.COMPANIES.get(ticker, ticker),
            "price":        f"${price:,.2f}" if price is not None else "—",
            "chg":          chg_str,
            "chg_color":    chg_color,
            "chg_raw":      price_chg,
            "bullish_pct":  f"{bullish_pct:.0f}%" if bullish_pct is not None else "—",
            "trends":       f"{trends_score:.0f}/100" if trends_score is not None else "—",
            "news_sent":    f"{news_sent:+.3f}" if news_sent is not None else "—",
            "news_sent_raw": news_sent,
            "signal":       signal,
            "sig_color":    sig_color,
        })
    return rows


# ── Ticker strip ───────────────────────────────────────────────────────────────
def build_ticker_strip_html(rows):
    sorted_rows = sorted(
        rows,
        key=lambda r: abs(r["chg_raw"]) if r["chg_raw"] is not None else 0,
        reverse=True,
    )
    top5 = sorted_rows[:5]

    def item_html(r):
        sig_color = r["sig_color"]
        chg_color = r["chg_color"]
        return (
            f'<span class="strip-item">'
            f'<span class="strip-ticker">{r["ticker"]}</span>'
            f'<span class="strip-sig" style="color:{sig_color}">{r["signal"]}</span>'
            f'<span class="strip-chg" style="color:{chg_color}">{r["chg"]}</span>'
            f'</span>'
            f'<span class="strip-sep" aria-hidden="true">|</span>'
        )

    items = "".join(item_html(r) for r in top5)
    # Triple content for seamless marquee loop
    track = items * 3

    return (
        f'<div class="ticker-strip-outer" aria-label="Top movers ticker strip">'
        f'<div class="strip-track">{track}</div>'
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

    last_upd = datetime.now().strftime("%H:%M")

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
      <span class="live-pulse" title="Live data" aria-label="Live data indicator"></span>
      <span class="chip-time">{last_upd}</span>
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
        ticker      = r["ticker"]
        sig         = r["signal"]
        sig_color   = r["sig_color"]
        border_top  = sig_color
        delay_ms    = i * 80
        svg         = build_sparkline_svg(ticker, sig_color)
        html += (
            f'<div class="spark-card" '
            f'style="border-top-color:{border_top};animation-delay:{delay_ms}ms">'

            f'<div class="spark-card-top">'
            f'<span class="spark-ticker">{ticker}</span>'
            f'<span class="spark-sig" style="color:{sig_color}">{sig}</span>'
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


# ── Signal table HTML ──────────────────────────────────────────────────────────
_TOOLTIPS = {
    "CHG %":     "1-day percentage change in closing price.",
    "BULLISH %": "Share of alt data signals currently skewing bullish for this ticker.",
    "TRENDS":    "Relative search interest score (0–100) from Google Trends; 100 = peak interest in the period.",
    "NEWS SENT": "Aggregate news sentiment score (−1 to +1); positive = predominantly bullish coverage.",
    "SIGNAL":    "Composite signal. BULLISH = majority of sources align positive; BEARISH = majority negative; NEUTRAL = mixed or insufficient data.",
}

def _th(label):
    if label in _TOOLTIPS:
        return (
            f'<div class="data-tbl-th">{label}'
            f'<span class="th-tip" tabindex="0">'
            f'<span class="th-tip-icon" aria-label="Definition for {label}">ⓘ</span>'
            f'<span class="th-tip-box" role="tooltip">{_TOOLTIPS[label]}</span>'
            f'</span></div>'
        )
    return f'<div class="data-tbl-th">{label}</div>'

def build_table_html(rows):
    headers = ["TICKER", "COMPANY", "PRICE", "CHG %", "BULLISH %", "TRENDS", "NEWS SENT", "SIGNAL", ""]
    head    = '<div class="data-tbl-head">' + "".join(_th(h) for h in headers) + '</div>'

    body = ""
    base_delay = 800
    for i, r in enumerate(rows):
        row_cls    = "data-tbl-row even" if i % 2 == 0 else "data-tbl-row odd"
        delay_ms   = base_delay + i * 80
        ticker     = r["ticker"]
        body += (
            f'<div class="{row_cls}" style="animation-delay:{delay_ms}ms">'
            f'<div class="data-tbl-td tkr">{ticker}</div>'
            f'<div class="data-tbl-td">{r["company"]}</div>'
            f'<div class="data-tbl-td num">{r["price"]}</div>'
            f'<div class="data-tbl-td num" style="color:{r["chg_color"]}">{r["chg"]}</div>'
            f'<div class="data-tbl-td num">{r["bullish_pct"]}</div>'
            f'<div class="data-tbl-td num">{r["trends"]}</div>'
            f'<div class="data-tbl-td num">{r["news_sent"]}</div>'
            f'<div class="data-tbl-td num" style="color:{r["sig_color"]};font-weight:600">{r["signal"]}</div>'
            f'<div class="data-tbl-td act">'
            f'<a href="?ticker={ticker}" class="view-btn">View Details</a>'
            f'</div>'
            f'</div>'
        )

    return f'<div class="data-tbl">{head}{body}</div>'


# ── Glossary ───────────────────────────────────────────────────────────────────
_GLOSSARY = [
    ("PRICE CHG %",
     "1-day percentage change in closing price relative to the prior trading day's close, sourced from Yahoo Finance."),
    ("BULLISH %",
     "Share of labeled StockTwits posts tagged Bullish for this ticker on the most recent collection date. Values above 55% are treated as a bullish signal; below 40% as bearish."),
    ("TRENDS",
     "Google Trends relative search interest, normalized to 0–100 within the 90-day period. 100 = peak search interest. A score 10%+ above the 7-day average is treated as an elevated-attention signal."),
    ("NEWS SENT",
     "Average VADER sentiment score across Yahoo Finance headlines on the most recent collection date. Range: −1.0 (strongly negative) to +1.0 (strongly positive). Values above +0.10 or below −0.10 trigger a signal vote."),
    ("SIGNAL",
     "Composite majority-vote signal across up to 4 sources. Each source contributes +1 (bullish) or −1 (bearish). Score ≥ +2 = BULLISH; ≤ −2 = BEARISH; otherwise NEUTRAL. Treat BULLISH as a weight of evidence, not a guarantee — most useful when corroborated by TRENDS and NEWS SENT moving in the same direction."),
]

def show_glossary():
    with st.expander("Metric Definitions"):
        rows_html = ""
        for i, (term, defn) in enumerate(_GLOSSARY):
            if i > 0:
                rows_html += '<div class="glossary-sep"></div>'
            rows_html += (
                f'<div class="glossary-term">{term}</div>'
                f'<div class="glossary-def">{defn}</div>'
            )
        st.markdown(
            f'<div class="glossary-grid">{rows_html}</div>',
            unsafe_allow_html=True,
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
      var v = easeOut(p) * target;
      el.textContent = prefix + v.toFixed(dec);
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = prefix + target.toFixed(dec);
    })(start);
  }

  setTimeout(function () {
    document.querySelectorAll('[data-countup-int]').forEach(function (el) {
      animateInt(el, parseInt(el.dataset.countupInt, 10));
    });
    document.querySelectorAll('[data-countup-float]').forEach(function (el) {
      var target = parseFloat(el.dataset.countupFloat);
      var dec    = parseInt(el.dataset.countupDec || '2', 10);
      var prefix = el.dataset.countupPrefix || '';
      animateFloat(el, target, dec, prefix);
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
            name="Price (normalized)",
            hovertemplate="%{y:.1f}<extra>Price (norm)</extra>",
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
        if mx != mn:
            rolling_n = (df["interest"].rolling(7, min_periods=1).mean() - mn) / (mx - mn) * 100
        else:
            rolling_n = pd.Series(50.0, index=df.index)
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
            name="Price (normalized)",
            hovertemplate="%{y:.1f}<extra>Price (norm)</extra>",
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

    sent  = df["avg_sentiment"].dropna()
    if len(sent) < 1:
        return None, True
    sparse = len(sent) < 3

    sent_n = norm_0_100(sent)

    # Position of sentiment=0 on the normalized 0-100 axis
    mn, mx = sent.min(), sent.max()
    neutral_pos = ((0 - mn) / (mx - mn) * 100) if mx != mn else 50.0
    neutral_pos = max(0.0, min(100.0, neutral_pos))

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
            name="Price (normalized)",
            hovertemplate="%{y:.1f}<extra>Price (norm)</extra>",
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
            fig.add_trace(go.Scatter(
                x=norm_0_100(p).index, y=norm_0_100(p), mode="lines",
                name="Price (norm)", line=dict(color=C3, width=2.5),
                hovertemplate="%{y:.1f}<extra>Price</extra>",
            ))
    if not trends_df.empty:
        n = norm_0_100(trends_df["interest"])
        fig.add_trace(go.Scatter(
            x=n.index, y=n, mode="lines", name="Trends (norm)",
            line=dict(color=C2, width=2.5),
            hovertemplate="%{y:.1f}<extra>Trends</extra>",
        ))
    if not st_df.empty and "net_sentiment" in st_df.columns:
        n = norm_0_100(st_df["net_sentiment"])
        fig.add_trace(go.Scatter(
            x=n.index, y=n, mode="lines+markers", name="StockTwits (norm)",
            line=dict(color=GREEN, width=2.5), marker=dict(size=6),
            hovertemplate="%{y:.1f}<extra>StockTwits</extra>",
        ))
    if not news_df.empty and "avg_sentiment" in news_df.columns:
        n = norm_0_100(news_df["avg_sentiment"])
        fig.add_trace(go.Scatter(
            x=n.index, y=n, mode="lines+markers", name="News (norm)",
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
    show_header()

    rows = build_summary()

    # B. Ticker strip
    st.markdown(build_ticker_strip_html(rows), unsafe_allow_html=True)

    # C. Market chips
    st.markdown(build_market_chips_html(rows), unsafe_allow_html=True)

    # D. Signal distribution
    st.plotly_chart(
        build_signal_dist_chart(rows),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    # E. Sparkline grid
    st.markdown('<div class="sec-label">Individual Ticker Signals</div>', unsafe_allow_html=True)
    st.markdown(build_sparkline_grid_html(rows), unsafe_allow_html=True)

    # F. Full signal table
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

    # G. Glossary
    show_glossary()

    # Animations JS
    st.markdown(build_animations_js(), unsafe_allow_html=True)


# ── Detail view ────────────────────────────────────────────────────────────────
def show_detail(ticker):
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

    # Chart 1 — Price
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

    # Chart 2 — StockTwits
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
        f"StockTwits users voluntarily tag posts as 'Bullish' or 'Bearish' — providing direct labels "
        f"rather than inferred tone. Both series and the price line are normalized to 0–100 for visual "
        f"comparison of direction and magnitude. Academic research has linked StockTwits sentiment to "
        f"next-day abnormal returns for high-attention stocks."
    )

    # Chart 3 — Google Trends
    st.markdown('<div class="sec-label">Google Trends Search Interest</div>', unsafe_allow_html=True)
    fig3 = chart_trends(ticker)
    if fig3:
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No Google Trends data available.")
    note(
        f"Search interest normalized to 0–100 within the 90-day period, alongside normalized price "
        f"(dotted). The dotted curve also shows the 7-day rolling average. Da, Engelberg &amp; Gao (2011) "
        f"linked retail search attention to short-term price pressure in <em>In Search of Attention</em>."
    )

    # Chart 4 — News sentiment
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
        f"VADER sentiment scores normalized to 0–100 alongside normalized price (dotted). The neutral "
        f"reference line shows the position of raw sentiment = 0 on the normalized axis. Bars above "
        f"the line are net-positive days; below are net-negative days."
    )

    # Chart 5 — Overlay
    st.markdown('<div class="sec-label">All Signals Overlaid (Normalized 0–100)</div>', unsafe_allow_html=True)
    fig5 = chart_overlay(ticker)
    st.plotly_chart(fig5, use_container_width=True, config={"displayModeBar": False})
    note(
        f"All four signals normalized to 0–100 and plotted together to reveal lead/lag relationships. "
        f"As data accumulates, this chart will show whether sentiment peaks tend to precede or follow "
        f"price movements — the core empirical question of this project."
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
