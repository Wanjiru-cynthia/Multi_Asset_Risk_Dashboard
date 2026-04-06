"""
Page 2 — Asset Class Drill-Down
  • Select an asset class
  • Live price charts and vol metrics from yfinance
  • Filtered event feed for that asset class
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from data.database import fetch_enriched_events
from data.market_data import fetch_latest_quotes, fetch_price_history, TICKERS
from dashboard.components.charts import (
    render_price_chart,
    render_vol_bars,
    render_returns_bars,
    severity_badge,
    direction_badge,
    ASSET_LABELS,
    SEV_COLORS,
)
from dashboard.components.macro_sidebar import render_macro_sidebar

st.set_page_config(page_title="Asset Drilldown | Risk Dashboard", layout="wide", page_icon="🔬")
render_macro_sidebar()

st.markdown('<h1 style="color:#4CC9F0">🔬 Asset Class Drill-Down</h1>', unsafe_allow_html=True)

# ── asset class selector ──────────────────────────────────────────────────────
ac_options = list(ASSET_LABELS.keys())
selected_ac = st.selectbox(
    "Select Asset Class",
    ac_options,
    format_func=lambda x: ASSET_LABELS.get(x, x),
)

col_ctrl1, col_ctrl2 = st.columns([1, 5])
with col_ctrl1:
    if st.button("🔄 Refresh Market Data"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")


# ── market quotes ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_quotes(ac: str) -> pd.DataFrame:
    return fetch_latest_quotes(asset_class=ac)


@st.cache_data(ttl=300)
def load_events(ac: str) -> pd.DataFrame:
    df = fetch_enriched_events(days=14, limit=500)
    if df.empty:
        return df
    return df[df["asset_class"] == ac]


quotes = load_quotes(selected_ac)
events = load_events(selected_ac)

# ── quote summary strip ───────────────────────────────────────────────────────
st.markdown(f"### {ASSET_LABELS[selected_ac]} — Live Quotes")

if quotes.empty:
    st.warning("Could not fetch market data. Check your internet connection.")
else:
    metric_cols = st.columns(len(quotes))
    for i, (_, row) in enumerate(quotes.iterrows()):
        with metric_cols[i]:
            price_str = f"{row['last_price']:.4f}" if row["last_price"] < 10 else f"{row['last_price']:.2f}"
            delta_str = f"{row['day_return_pct']:+.2f}%"
            delta_color = "normal" if row["day_return_pct"] >= 0 else "inverse"
            st.metric(
                label=row["name"],
                value=price_str,
                delta=delta_str,
                delta_color=delta_color,
            )
            st.caption(f"Vol (30d ann): {row['vol_30d_ann']:.1f}%")

st.markdown("<br>", unsafe_allow_html=True)

# ── vol comparison + returns ──────────────────────────────────────────────────
col_vol, col_ret = st.columns(2)
with col_vol:
    if not quotes.empty:
        st.plotly_chart(render_vol_bars(quotes, selected_ac), use_container_width=True)

with col_ret:
    all_quotes = fetch_latest_quotes()  # cached separately
    if not all_quotes.empty:
        st.plotly_chart(render_returns_bars(all_quotes), use_container_width=True)

st.markdown("---")

# ── individual ticker price charts ───────────────────────────────────────────
st.markdown(f"### Price Charts — {ASSET_LABELS[selected_ac]}")

ticker_map = TICKERS.get(selected_ac, {})
chart_cols = st.columns(2)

@st.cache_data(ttl=600)
def load_hist(ticker: str) -> pd.DataFrame:
    return fetch_price_history(ticker, period="30d", interval="1d")

for i, (ticker, name) in enumerate(ticker_map.items()):
    with chart_cols[i % 2]:
        hist = load_hist(ticker)
        st.plotly_chart(render_price_chart(ticker, name, hist), use_container_width=True)

st.markdown("---")

# ── filtered event feed ───────────────────────────────────────────────────────
st.markdown(f"### 📰 Events — {ASSET_LABELS[selected_ac]} (last 14 days)")

if events.empty:
    st.info(f"No classified events for {ASSET_LABELS[selected_ac]} in the last 14 days.")
else:
    sev_min = st.slider("Min Severity", 1, 5, 1, key="drilldown_sev")
    filtered = events[events["severity"] >= sev_min] if "severity" in events.columns else events

    st.caption(f"Showing {len(filtered)} events")
    for _, ev in filtered.iterrows():
        sev = int(ev.get("severity") or 1)
        border_color = SEV_COLORS.get(sev, "#555")
        pub = str(ev.get("published_at", ""))[:10]
        source = ev.get("source", "Unknown")
        rt = str(ev.get("risk_type") or "—").title()
        sent_lbl = str(ev.get("sentiment_label") or "—").title()
        conf = ev.get("sentiment_confidence")
        conf_str = f"{conf:.0%}" if conf else "—"
        url = ev.get("url", "#")
        ev_id = ev.get("id")

        col_ev, col_detail = st.columns([9, 1])
        with col_ev:
            st.markdown(
                f"""
                <div style="background:#161B22;border-left:4px solid {border_color};
                            padding:10px 14px;margin-bottom:8px;border-radius:4px">
                  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:5px">
                    {severity_badge(sev)}&nbsp;{direction_badge(ev.get("direction"))}
                    <span style="color:#888;font-size:0.75rem">{rt}</span>
                    <span style="color:#555;font-size:0.7rem;margin-left:auto">{source} · {pub}</span>
                  </div>
                  <a href="{url}" target="_blank"
                     style="color:#C9D1D9;font-size:0.88rem;text-decoration:none;font-weight:500">
                    {ev.get('title', '—')}
                  </a>
                  <div style="margin-top:5px;color:#666;font-size:0.72rem">
                    Sentiment: <span style="color:#aaa">{sent_lbl}</span> ({conf_str})
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_detail:
            if ev_id:
                if st.button("Detail", key=f"detail_{ev_id}"):
                    st.session_state["selected_event_id"] = ev_id
                    st.switch_page("pages/3_Event_Detail.py")
