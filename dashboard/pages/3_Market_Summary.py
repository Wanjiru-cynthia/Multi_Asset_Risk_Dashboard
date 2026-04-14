"""
Page 3 — Market Summary
  • Equities, Fixed Income, FX, Commodities — live quotes with last-updated timestamps
  • 30-day price charts per ticker
  • Cross-asset return comparison
  • FRED macro indicators (VIX, yield curve, credit spreads, DXY)
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data.market_data import fetch_latest_quotes, fetch_price_history, TICKERS
from data.macro_data import fetch_latest_macro, fetch_macro_history, FRED_SERIES
from dashboard.components.macro_sidebar import render_macro_sidebar

st.set_page_config(page_title="Market Summary", page_icon="📊", layout="wide")
render_macro_sidebar()

st.markdown('<h1 style="color:#2A9D8F">📊 Market Summary</h1>', unsafe_allow_html=True)

ASSET_LABELS = {"equities":"Equities","fixed_income":"Fixed Income",
                "fx":"FX","commodities":"Commodities"}
FRED_COLORS  = {"VIXCLS":"#E63946","T10Y2Y":"#4CC9F0",
                "BAMLH0A0HYM2":"#F4A261","DTWEXBGS":"#7209B7",
                "DGS10":"#4361EE","FEDFUNDS":"#2A9D8F"}

col_r, col_c = st.columns([5,1])
with col_c:
    if st.button("🔄 Refresh All"):
        st.cache_data.clear(); st.rerun()

st.markdown("---")


@st.cache_data(ttl=300)
def load_quotes():
    df = fetch_latest_quotes()
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return df, fetched_at

@st.cache_data(ttl=600)
def load_hist(ticker):
    return fetch_price_history(ticker, period="30d", interval="1d")

@st.cache_data(ttl=900)
def load_macro():
    return fetch_latest_macro(), fetch_macro_history(lookback_days=90)


quotes, quotes_ts = load_quotes()

# ── cross-asset returns bar ────────────────────────────────────────────────────
st.markdown("### Cross-Asset Returns (30-Day)")
st.caption(f"Last updated: {quotes_ts}")

if not quotes.empty:
    df_sorted = quotes.sort_values("period_return_pct", ascending=True)
    colors = ["#E63946" if r < 0 else "#2A9D8F" for r in df_sorted["period_return_pct"]]
    fig = go.Figure(go.Bar(
        x=df_sorted["period_return_pct"],
        y=df_sorted["name"],
        orientation="h",
        marker_color=colors,
        text=df_sorted["period_return_pct"].round(2).astype(str) + "%",
        textposition="outside",
    ))
    fig.add_vline(x=0, line_color="#444", line_width=1)
    fig.update_layout(
        xaxis_title="Return (%)",
        plot_bgcolor="#0D1117", paper_bgcolor="#0D1117",
        font=dict(color="#C9D1D9",size=11),
        height=460, margin=dict(t=10,b=40,l=160,r=80),
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── per-asset-class tabs ───────────────────────────────────────────────────────
tabs = st.tabs([ASSET_LABELS[ac] for ac in TICKERS])

for tab, (ac, ticker_map) in zip(tabs, TICKERS.items()):
    with tab:
        # Quote strip
        ac_quotes = quotes[quotes["asset_class"] == ac] if not quotes.empty else pd.DataFrame()
        if not ac_quotes.empty:
            mcols = st.columns(len(ac_quotes))
            for col, (_, row) in zip(mcols, ac_quotes.iterrows()):
                price = f"{row['last_price']:.4f}" if row["last_price"] < 10 else f"{row['last_price']:.2f}"
                delta_color = "normal" if row["day_return_pct"] >= 0 else "inverse"
                col.metric(row["name"], price, f"{row['day_return_pct']:+.2f}%",
                           delta_color=delta_color)
                col.caption(f"Vol 30d: {row['vol_30d_ann']:.1f}%")
        else:
            st.warning("Market data unavailable.")

        st.caption(f"Data as of {quotes_ts}")
        st.markdown("<br>", unsafe_allow_html=True)

        # Price charts (2-col grid)
        chart_cols = st.columns(2)
        for i, (ticker, name) in enumerate(ticker_map.items()):
            with chart_cols[i % 2]:
                hist = load_hist(ticker)
                if hist.empty:
                    st.warning(f"No data for {ticker}")
                    continue

                close = hist.get("Close", pd.Series())
                fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                     vertical_spacing=0.05, row_heights=[0.75,0.25])
                fig2.add_trace(go.Candlestick(
                    x=hist.index,
                    open=hist.get("Open", close),
                    high=hist.get("High", close),
                    low=hist.get("Low",  close),
                    close=close,
                    name=ticker,
                    increasing_line_color="#2A9D8F",
                    decreasing_line_color="#E63946",
                ), row=1, col=1)

                if len(hist) >= 20:
                    sma = close.rolling(20).mean()
                    fig2.add_trace(go.Scatter(x=hist.index, y=sma, name="SMA20",
                        line=dict(color="#F4A261",width=1.5,dash="dot")), row=1, col=1)

                if "Volume" in hist.columns:
                    vol_colors = ["#2A9D8F" if c >= o else "#E63946"
                                  for c,o in zip(close, hist.get("Open",close))]
                    fig2.add_trace(go.Bar(x=hist.index, y=hist["Volume"],
                        marker_color=vol_colors, showlegend=False), row=2, col=1)

                fig2.update_layout(
                    title=f"{name} ({ticker})",
                    xaxis_rangeslider_visible=False,
                    plot_bgcolor="#0D1117", paper_bgcolor="#0D1117",
                    font=dict(color="#C9D1D9",size=10),
                    height=380, margin=dict(t=40,b=20,l=50,r=10),
                    legend=dict(orientation="h",yanchor="bottom",y=1.02),
                )
                st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── FRED macro panel ───────────────────────────────────────────────────────────
st.markdown("### Macro Backdrop — FRED Indicators")
macro_latest, macro_hist = load_macro()

DISPLAY = [
    ("VIXCLS",       "Elevated >25 · Crisis >35"),
    ("T10Y2Y",       "Negative = yield curve inverted"),
    ("BAMLH0A0HYM2", "HY OAS >500bps = elevated credit stress"),
    ("DTWEXBGS",     "Broad trade-weighted USD"),
    ("DGS10",        "Risk-free benchmark"),
    ("FEDFUNDS",     "Current Fed policy rate"),
]

metric_cols = st.columns(len(DISPLAY))
for col, (sid, tooltip) in zip(metric_cols, DISPLAY):
    info = macro_latest.get(sid, {})
    val  = info.get("value")
    name = info.get("name", sid).split("(")[0].strip()
    date = info.get("date", "—")
    color = FRED_COLORS.get(sid, "#888")
    with col:
        if val is not None:
            st.markdown(
                f'<div style="background:#161B22;padding:12px;border-radius:8px;'
                f'border-top:3px solid {color};text-align:center">'
                f'<div style="font-size:0.68rem;color:#888;margin-bottom:4px">{name}</div>'
                f'<div style="font-size:1.5rem;font-weight:bold;color:{color}">{val:.2f}</div>'
                f'<div style="font-size:0.62rem;color:#555;margin-top:3px">{date}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="background:#161B22;padding:12px;border-radius:8px;'
                f'border-top:3px solid #333;text-align:center">'
                f'<div style="font-size:0.68rem;color:#888">{name}</div>'
                f'<div style="color:#555;font-size:0.85rem">N/A</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

st.markdown("<br>", unsafe_allow_html=True)

# Historical charts (2-col grid)
if macro_hist:
    chart_pairs = [DISPLAY[i:i+2] for i in range(0, len(DISPLAY), 2)]
    for pair in chart_pairs:
        c1, c2 = st.columns(2)
        for col_widget, (sid, tooltip) in zip([c1, c2], pair):
            with col_widget:
                series = macro_hist.get(sid)
                if series is None or series.empty:
                    st.info(f"No history for {sid}")
                    continue
                color = FRED_COLORS.get(sid, "#4CC9F0")
                r, g, b = (
                    int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
                ) if color.startswith("#") else (76,201,240)
                fill = f"rgba({r},{g},{b},0.1)"
                fig = go.Figure(go.Scatter(
                    x=series.index, y=series.values,
                    mode="lines", line=dict(color=color,width=2),
                    fill="tozeroy", fillcolor=fill,
                ))
                name_full = FRED_SERIES.get(sid,{}).get("name", sid)
                if sid == "T10Y2Y":
                    fig.add_hline(y=0, line_dash="dash", line_color="#E63946",
                                  line_width=1, annotation_text="Inversion",
                                  annotation_font_color="#E63946")
                elif sid == "VIXCLS":
                    fig.add_hline(y=25, line_dash="dot", line_color="#F4A261",
                                  line_width=1, annotation_text="Elevated")
                    fig.add_hline(y=35, line_dash="dot", line_color="#E63946",
                                  line_width=1, annotation_text="Crisis")
                fig.update_layout(
                    title=name_full, height=220,
                    plot_bgcolor="#0D1117", paper_bgcolor="#0D1117",
                    font=dict(color="#C9D1D9",size=10),
                    margin=dict(t=40,b=30,l=50,r=10), showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)
                st.caption(tooltip)
else:
    st.info("Add FRED_API_KEY to `.env` or Streamlit Cloud secrets for macro history charts.")

st.markdown("---")
st.caption("Market data: yfinance · Macro data: FRED (St. Louis Fed)")
