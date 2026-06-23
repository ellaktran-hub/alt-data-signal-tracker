"""
dashboard.py
Bloomberg-style research dashboard for the Alt Data Signal Tracker.
Run with: python3 -m streamlit run dashboard.py
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
import config

DATA_DIR = Path(__file__).parent / "data"

# ── Page config (must be the first Streamlit call) ────────────────────────────
st.set_page_config(
    page_title="Alt Data Signal Tracker",
    page_icon="▲",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = "#0b0e1a"
SURFACE = "#0f1623"
CARD    = "#111827"
BORDER  = "#1e2d40"
TEXT    = "#c9d1d9"
MUTED   = "#4b5563"
GREEN   = "#00d4aa"
RED     = "#f87171"
BLUE    = "#58a6ff"
ORANGE  = "#f0883e"
PURPLE  = "#bc8cff"
YELLOW  = "#e3b341"

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  .stApp {{ background-color: {BG}; }}
  .block-container {{ padding: 1.2rem 2rem 2rem; max-width: 1440px; }}

  /* Hide Streamlit chrome */
  #MainMenu, footer, [data-testid="stToolbar"] {{ visibility: hidden; }}

  /* Metric cards */
  [data-testid="metric-container"] {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 12px 16px;
  }}
  [data-testid="stMetricLabel"] > div {{
    color: {MUTED} !important;
    font-size: 0.68rem !important;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    font-family: monospace !important;
  }}
  [data-testid="stMetricValue"] > div {{
    color: {TEXT} !important;
    font-size: 1.25rem !important;
    font-weight: 700;
    font-family: monospace !important;
  }}
  [data-testid="stMetricDelta"] > div {{
    font-size: 0.78rem !important;
    font-family: monospace !important;
  }}

  /* Section labels */
  .sec-label {{
    color: {MUTED};
    font-family: monospace;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 1.2rem 0 0.4rem;
    border-bottom: 1px solid {BORDER};
    padding-bottom: 4px;
  }}

  /* Research header */
  .rh {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-left: 3px solid {BLUE};
    border-radius: 5px;
    padding: 14px 20px;
    margin-bottom: 1rem;
  }}
  .rh-title {{
    color: {TEXT};
    font-family: monospace;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin: 0 0 8px;
  }}
  .rh-body {{
    color: {MUTED};
    font-family: monospace;
    font-size: 0.79rem;
    line-height: 1.75;
    margin: 0 0 6px;
  }}
  .rh-status {{
    color: {GREEN};
    font-family: monospace;
    font-size: 0.68rem;
    letter-spacing: 0.06em;
  }}

  /* Chart annotation text */
  .chart-note {{
    color: {MUTED};
    font-family: monospace;
    font-size: 0.78rem;
    line-height: 1.7;
    margin: 2px 0 1.2rem;
    padding: 8px 14px;
    border-left: 2px solid {BORDER};
    background: {SURFACE};
    border-radius: 0 4px 4px 0;
  }}

  /* Sparse-data warning */
  .sparse-note {{
    color: {ORANGE};
    font-family: monospace;
    font-size: 0.76rem;
    line-height: 1.65;
    margin: 2px 0 0.8rem;
    padding: 8px 14px;
    border-left: 2px solid {ORANGE};
    background: rgba(240,136,62,0.06);
    border-radius: 0 4px 4px 0;
  }}

  /* Signal badges in table */
  .sig-bull {{ color: {GREEN}; font-weight: 700; }}
  .sig-bear {{ color: {RED};   font-weight: 700; }}
  .sig-neut {{ color: {MUTED}; font-weight: 700; }}

  /* Buttons */
  .stButton > button {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    color: {TEXT};
    font-family: monospace;
    font-size: 0.78rem;
    border-radius: 4px;
    padding: 4px 14px;
  }}
  .stButton > button:hover {{
    border-color: {BLUE};
    color: {BLUE};
    background: {CARD};
  }}

  /* Selectbox label */
  [data-testid="stSelectbox"] label {{
    color: {MUTED} !important;
    font-family: monospace !important;
    font-size: 0.68rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }}

  /* Divider */
  hr {{ border-color: {BORDER}; margin: 0.6rem 0; }}
</style>
""", unsafe_allow_html=True)


# ── Plotly layout factory ─────────────────────────────────────────────────────
def chart_layout(title="", height=270):
    return dict(
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        font=dict(color=TEXT, family="monospace", size=11),
        title=dict(text=title, font=dict(size=11, color=MUTED), x=0, xanchor="left", y=0.97),
        xaxis=dict(
            gridcolor=BORDER, linecolor=BORDER,
            tickfont=dict(size=9, color=MUTED), showgrid=True, zeroline=False,
        ),
        yaxis=dict(
            gridcolor=BORDER, linecolor=BORDER,
            tickfont=dict(size=9, color=MUTED), showgrid=True, zeroline=False,
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", bordercolor=BORDER,
            font=dict(size=9, color=MUTED), orientation="h",
            yanchor="bottom", y=1.01, xanchor="right", x=1,
        ),
        margin=dict(l=52, r=16, t=30, b=36),
        height=height,
        hovermode="x unified",
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=BORDER, font=dict(family="monospace", size=11)),
    )


# ── Data loaders ──────────────────────────────────────────────────────────────
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


# ── Signal & helpers ──────────────────────────────────────────────────────────
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
    score = sum(votes)
    if score >= 2:
        return "BULLISH"
    if score <= -2:
        return "BEARISH"
    return "NEUTRAL"

def note(text):
    st.markdown(f'<div class="chart-note">{text}</div>', unsafe_allow_html=True)

def sparse_note():
    st.markdown(
        '<div class="sparse-note">⚠ Data still accumulating — fewer than 3 days collected. '
        'This chart will fill in as the daily pipeline runs each morning. '
        'Signals become meaningful for analysis after ~30 days of data.</div>',
        unsafe_allow_html=True,
    )


# ── Summary data ──────────────────────────────────────────────────────────────
# No @st.cache_data here — Streamlit crashes when a cached function calls
# other cached functions (UnhashableTypeError on the inner return values).
def build_summary():
    rows = []
    for ticker in config.TICKERS:
        price_df  = load_prices(ticker)
        st_df     = load_stocktwits(ticker)
        trends_df = load_trends(ticker)
        news_df   = load_news(ticker)

        price = safe_last(price_df, "close_price")
        if not price_df.empty and len(price_df["close_price"].dropna()) >= 2:
            series    = price_df["close_price"].dropna()
            price_chg = (series.iloc[-1] - series.iloc[-2]) / series.iloc[-2] * 100
        else:
            price_chg = None

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

        rows.append({
            "TICKER":    ticker,
            "PRICE":     f"${price:,.2f}"      if price is not None    else "—",
            "CHG %":     f"{price_chg:+.2f}%"  if price_chg is not None else "—",
            "BULLISH %": f"{bullish_pct:.0f}%"  if bullish_pct is not None else "—",
            "TRENDS":    f"{trends_score:.0f}/100" if trends_score is not None else "—",
            "NEWS SENT": f"{news_sent:+.3f}"    if news_sent is not None else "—",
            "SIGNAL":    signal,
        })
    return pd.DataFrame(rows)


# ── Chart builders ────────────────────────────────────────────────────────────
def chart_price(ticker):
    df = load_prices(ticker)
    if df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["close_price"],
        mode="lines",
        line=dict(color=BLUE, width=1.8),
        fill="tozeroy", fillcolor="rgba(88,166,255,0.07)",
        name="Close",
        hovertemplate="$%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(**chart_layout(f"{ticker}  ·  Daily Close Price (USD)"))
    fig.update_yaxes(tickprefix="$")
    return fig


def chart_stocktwits(ticker):
    df = load_stocktwits(ticker)
    if df.empty or "bullish_count" not in df.columns:
        return None, True
    df = df.copy()
    total = df["message_count"].replace(0, np.nan)
    df["bull_pct"] = (df["bullish_count"] / total * 100).fillna(0)
    df["bear_pct"] = (df["bearish_count"] / total * 100).fillna(0)
    sparse = len(df) < 3
    mode   = "lines+markers" if sparse else "lines"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["bull_pct"],
        mode=mode, line=dict(color=GREEN, width=1.8),
        fill="tozeroy", fillcolor="rgba(0,212,170,0.12)",
        name="Bullish %", hovertemplate="%{y:.1f}%<extra>Bullish</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["bear_pct"],
        mode=mode, line=dict(color=RED, width=1.8),
        fill="tozeroy", fillcolor="rgba(248,113,113,0.10)",
        name="Bearish %", hovertemplate="%{y:.1f}%<extra>Bearish</extra>",
    ))
    fig.update_layout(**chart_layout(f"{ticker}  ·  StockTwits Bullish% vs Bearish%"))
    fig.update_yaxes(ticksuffix="%", range=[0, 105])
    return fig, sparse


def chart_trends(ticker):
    df = load_trends(ticker)
    if df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["interest"],
        mode="lines",
        line=dict(color=ORANGE, width=1.8),
        fill="tozeroy", fillcolor="rgba(240,136,62,0.07)",
        name="Search Interest",
        hovertemplate="%{y:.0f}/100<extra></extra>",
    ))
    if len(df) >= 7:
        avg = df["interest"].rolling(7, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=df.index, y=avg,
            mode="lines", line=dict(color=MUTED, width=1, dash="dot"),
            name="7d avg", hovertemplate="%{y:.1f}<extra>7d avg</extra>",
        ))
    fig.update_layout(**chart_layout(f"{ticker}  ·  Google Trends Search Interest (0–100)"))
    fig.update_yaxes(range=[0, 105])
    return fig


def chart_news(ticker):
    df = load_news(ticker)
    if df.empty or "avg_sentiment" not in df.columns:
        return None, True
    sparse = len(df) < 3
    colors = [GREEN if v >= 0 else RED for v in df["avg_sentiment"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df.index, y=df["avg_sentiment"],
        marker_color=colors,
        name="Sentiment",
        hovertemplate="%{y:+.3f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=BORDER, line_width=1)
    fig.update_layout(**chart_layout(f"{ticker}  ·  News Headline Sentiment (VADER, –1 to +1)"))
    fig.update_yaxes(range=[-1.1, 1.1])
    return fig, sparse


def norm_0_100(series):
    s = series.dropna()
    if len(s) < 2:
        return s
    mn, mx = s.min(), s.max()
    return pd.Series(50.0, index=s.index) if mx == mn else (s - mn) / (mx - mn) * 100


def chart_overlay(ticker):
    price_df  = load_prices(ticker)
    trends_df = load_trends(ticker)
    st_df     = load_stocktwits(ticker)
    news_df   = load_news(ticker)
    fig       = go.Figure()

    if not price_df.empty:
        p = price_df["close_price"].dropna()
        if len(p) >= 2:
            ret = (p / p.iloc[0] - 1) * 100
            n   = norm_0_100(ret)
            fig.add_trace(go.Scatter(
                x=n.index, y=n, mode="lines", name="Price (norm)",
                line=dict(color=BLUE, width=2),
                hovertemplate="%{y:.1f}<extra>Price</extra>",
            ))

    if not trends_df.empty:
        n = norm_0_100(trends_df["interest"])
        fig.add_trace(go.Scatter(
            x=n.index, y=n, mode="lines", name="Trends (norm)",
            line=dict(color=ORANGE, width=1.6),
            hovertemplate="%{y:.1f}<extra>Trends</extra>",
        ))

    if not st_df.empty and "net_sentiment" in st_df.columns:
        n = norm_0_100(st_df["net_sentiment"])
        fig.add_trace(go.Scatter(
            x=n.index, y=n, mode="lines+markers", name="StockTwits (norm)",
            line=dict(color=YELLOW, width=1.6), marker=dict(size=5),
            hovertemplate="%{y:.1f}<extra>StockTwits</extra>",
        ))

    if not news_df.empty and "avg_sentiment" in news_df.columns:
        n = norm_0_100(news_df["avg_sentiment"])
        fig.add_trace(go.Scatter(
            x=n.index, y=n, mode="lines+markers", name="News (norm)",
            line=dict(color=PURPLE, width=1.6), marker=dict(size=5),
            hovertemplate="%{y:.1f}<extra>News Sent.</extra>",
        ))

    layout = chart_layout(f"{ticker}  ·  All Signals Overlaid (normalized 0–100)", height=320)
    layout["yaxis"]["title"] = dict(text="Signal Strength (normalized)", font=dict(size=9, color=MUTED))
    fig.update_layout(**layout)
    fig.update_yaxes(range=[-5, 108])
    return fig


# ── Header ────────────────────────────────────────────────────────────────────
def show_header():
    from datetime import date
    st.markdown(f"""
    <div class="rh">
      <div class="rh-title">Alt Data Signal Tracker</div>
      <div class="rh-body">
        This research project tests whether <em>alternative data</em> — community sentiment from StockTwits,
        search interest from Google Trends, and news headline tone scored via NLP — carries predictive
        information about short-term equity price movements for 10 consumer stocks. Each signal is collected
        daily via an automated pipeline and compared against closing price data from Yahoo Finance. The central
        research question: do retail investor sentiment and public search behavior lead or lag stock price
        changes, and if so, by how many days?
      </div>
      <div class="rh-status">
        LAST UPDATED: {date.today().strftime('%Y-%m-%d')}
        &nbsp;·&nbsp; {len(config.TICKERS)} TICKERS
        &nbsp;·&nbsp; 4 SIGNALS
        &nbsp;·&nbsp; PIPELINE ACTIVE (DAILY 06:30)
        &nbsp;·&nbsp; SENTIMENT ACCUMULATING FROM 2026-06-22
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── Summary view ──────────────────────────────────────────────────────────────
def show_summary():
    show_header()
    st.markdown('<div class="sec-label">Market Overview — click a row to open stock detail</div>', unsafe_allow_html=True)

    summary = build_summary()

    def style_signal(df):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        for i, sig in enumerate(df["SIGNAL"]):
            if sig == "BULLISH":
                styles.iloc[i, df.columns.get_loc("SIGNAL")] = f"color: {GREEN}; font-weight: bold"
            elif sig == "BEARISH":
                styles.iloc[i, df.columns.get_loc("SIGNAL")] = f"color: {RED}; font-weight: bold"
            else:
                styles.iloc[i, df.columns.get_loc("SIGNAL")] = f"color: {MUTED}; font-weight: bold"
        return styles

    styled = summary.style.apply(style_signal, axis=None)

    event = st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        height=400,
    )

    if event.selection.rows:
        idx = event.selection.rows[0]
        st.session_state.ticker = config.TICKERS[idx]
        st.session_state.view   = "detail"
        st.rerun()

    st.markdown(f"""
    <div class="chart-note" style="margin-top:0.6rem;">
      <strong>How the Signal is computed:</strong>
      StockTwits bullish% &gt; 55% = +1 vote · bullish% &lt; 40% = –1 vote.
      News sentiment &gt; +0.10 = +1 vote · &lt; –0.10 = –1 vote.
      Google Trends &gt; 10% above 7-day average = +1 vote · &gt; 10% below = –1 vote.
      Price change yesterday &gt; +0.5% = +1 vote · &lt; –0.5% = –1 vote.
      &nbsp;→&nbsp; Score ≥ +2 = <span style="color:{GREEN}">BULLISH</span> ·
      ≤ –2 = <span style="color:{RED}">BEARISH</span> · otherwise
      <span style="color:{MUTED}">NEUTRAL</span>.
    </div>
    """, unsafe_allow_html=True)


# ── Detail view ───────────────────────────────────────────────────────────────
def show_detail(ticker):
    show_header()

    col_back, col_drop, col_spacer = st.columns([1, 2, 8])
    with col_back:
        if st.button("← Summary"):
            st.session_state.view = "summary"
            st.rerun()
    with col_drop:
        new_ticker = st.selectbox(
            "Switch ticker",
            config.TICKERS,
            index=config.TICKERS.index(ticker),
            label_visibility="visible",
        )
        if new_ticker != ticker:
            st.session_state.ticker = new_ticker
            st.rerun()

    st.markdown("---")

    # ── Snapshot metrics ──────────────────────────────────────────────
    price_df  = load_prices(ticker)
    st_df     = load_stocktwits(ticker)
    trends_df = load_trends(ticker)
    news_df   = load_news(ticker)

    price = safe_last(price_df, "close_price")
    if not price_df.empty and len(price_df["close_price"].dropna()) >= 2:
        series    = price_df["close_price"].dropna()
        price_chg = (series.iloc[-1] - series.iloc[-2]) / series.iloc[-2] * 100
    else:
        price_chg = None

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
    signal_label = {"BULLISH": "▲ BULLISH", "BEARISH": "▼ BEARISH", "NEUTRAL": "→ NEUTRAL"}[signal]

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric(
            "Price",
            f"${price:,.2f}" if price is not None else "—",
            f"{price_chg:+.2f}%" if price_chg is not None else None,
        )
    with m2:
        st.metric("StockTwits Bullish%", f"{bullish_pct:.0f}%" if bullish_pct is not None else "—")
    with m3:
        st.metric("Google Trends", f"{trends_score:.0f}/100" if trends_score is not None else "—")
    with m4:
        st.metric("News Sentiment", f"{news_sent:+.3f}" if news_sent is not None else "—")
    with m5:
        signal_color = GREEN if signal == "BULLISH" else (RED if signal == "BEARISH" else MUTED)
        st.markdown(f"""
        <div style="background:{CARD}; border:1px solid {BORDER}; border-radius:5px;
                    padding:12px 16px; height:100%;">
          <div style="color:{MUTED}; font-size:0.68rem; text-transform:uppercase;
                      letter-spacing:0.09em; font-family:monospace; margin-bottom:6px;">
            Composite Signal
          </div>
          <div style="color:{signal_color}; font-size:1.25rem; font-weight:700; font-family:monospace;">
            {signal_label}
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Chart 1: Price ────────────────────────────────────────────────
    st.markdown('<div class="sec-label">Chart 1 — Price History</div>', unsafe_allow_html=True)
    fig1 = chart_price(ticker)
    if fig1:
        st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No price data available.")
    note(
        f"Daily closing price for <strong>{ticker}</strong> over the past 90 days, sourced from Yahoo Finance "
        f"via the <em>yfinance</em> library. Price is the baseline signal in this research — all sentiment and "
        f"search signals are compared against subsequent price moves to test whether they carry predictive "
        f"information. A sentiment signal that consistently precedes price moves by 1–5 trading days would be "
        f"considered economically meaningful."
    )

    # ── Chart 2: StockTwits ───────────────────────────────────────────
    st.markdown('<div class="sec-label">Chart 2 — StockTwits Community Sentiment</div>', unsafe_allow_html=True)
    fig2, sparse2 = chart_stocktwits(ticker)
    if fig2:
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No StockTwits data yet.")
    if sparse2:
        sparse_note()
    note(
        f"StockTwits is a social media platform used exclusively by retail equity traders, with over 6 million "
        f"registered users. Unlike general social media, users can voluntarily tag posts as 'Bullish' or "
        f"'Bearish' when discussing a ticker — providing a direct sentiment label rather than inferred tone. "
        f"This chart shows the daily percentage of labeled posts that were bullish (green) vs bearish (red). "
        f"Academic research has found StockTwits sentiment to be a statistically significant predictor of "
        f"next-day abnormal returns for high-attention stocks."
    )

    # ── Chart 3: Google Trends ────────────────────────────────────────
    st.markdown('<div class="sec-label">Chart 3 — Google Trends Search Interest</div>', unsafe_allow_html=True)
    fig3 = chart_trends(ticker)
    if fig3:
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No Google Trends data available.")
    note(
        f"Google Trends measures how frequently a term is searched relative to its own historical peak — a score "
        f"of 100 represents maximum search interest for the period; 50 represents half of that peak. The dotted "
        f"line is the 7-day rolling average, providing a baseline for identifying above- or below-normal "
        f"attention. Search interest often spikes around earnings announcements, product launches, or macro "
        f"events, making it a proxy for retail investor attention — which Da, Engelberg &amp; Gao (2011) linked "
        f"to short-term price pressure in their seminal paper <em>In Search of Attention</em>."
    )

    # ── Chart 4: News sentiment ───────────────────────────────────────
    st.markdown('<div class="sec-label">Chart 4 — News Headline Sentiment</div>', unsafe_allow_html=True)
    fig4, sparse4 = chart_news(ticker)
    if fig4:
        st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No news data yet.")
    if sparse4:
        sparse_note()
    note(
        f"Each bar represents the average VADER sentiment score across all Yahoo Finance news headlines "
        f"published for {ticker} on that day. VADER (Valence Aware Dictionary and sEntiment Reasoner) is an "
        f"NLP lexicon designed specifically for short financial and social media text — it scores each headline "
        f"from –1.0 (strongly negative) to +1.0 (strongly positive). Green bars indicate net-positive news "
        f"days; red bars indicate net-negative days. News sentiment is widely used in quantitative finance "
        f"as a signal orthogonal to price momentum, particularly in event-driven strategies."
    )

    # ── Chart 5: Overlay ──────────────────────────────────────────────
    st.markdown('<div class="sec-label">Chart 5 — All Signals Overlaid (Normalized 0–100)</div>', unsafe_allow_html=True)
    fig5 = chart_overlay(ticker)
    st.plotly_chart(fig5, use_container_width=True, config={"displayModeBar": False})
    note(
        f"All four signals normalized to a common 0–100 scale and plotted together to reveal visual "
        f"lead/lag relationships. Price is shown as normalized cumulative return from day 1 of the 90-day "
        f"window. Google Trends and StockTwits net sentiment are normalized relative to their own "
        f"min/max over the period. As sentiment and news data accumulate over the coming weeks, this chart "
        f"will make it visually clear whether community sentiment peaks and troughs tend to precede — or "
        f"follow — price movements. That temporal relationship is the core empirical question of this project."
    )


# ── Session state & routing ───────────────────────────────────────────────────
if "view" not in st.session_state:
    st.session_state.view = "summary"
if "ticker" not in st.session_state:
    st.session_state.ticker = config.TICKERS[0]

def has_any_data():
    return DATA_DIR.exists() and any(DATA_DIR.glob("prices_*.csv"))

try:
    if not has_any_data():
        show_header()
        st.markdown(f"""
        <div style="background:{CARD}; border:1px solid {BORDER}; border-left:3px solid {ORANGE};
                    border-radius:5px; padding:20px 24px; margin-top:1rem; font-family:monospace;">
          <div style="color:{ORANGE}; font-size:0.72rem; text-transform:uppercase;
                      letter-spacing:0.1em; margin-bottom:10px;">Pipeline Status</div>
          <div style="color:{TEXT}; font-size:1rem; font-weight:600; margin-bottom:8px;">
            Data pipeline not yet run — check back after the first scheduled update.
          </div>
          <div style="color:{MUTED}; font-size:0.8rem; line-height:1.7;">
            The automated pipeline runs daily at 06:30 and pushes fresh data to GitHub.
            Once data appears, this dashboard will display 90 days of price history,
            Google Trends, StockTwits sentiment, and news headline scores for all 10 tickers.
          </div>
        </div>
        """, unsafe_allow_html=True)
    elif st.session_state.view == "summary":
        show_summary()
    else:
        show_detail(st.session_state.ticker)
except Exception as e:
    st.error(
        f"Dashboard encountered an error: `{e}`\n\n"
        "If this is a fresh deployment, data files may still be loading. "
        "Try refreshing the page in 30 seconds."
    )
    raise
