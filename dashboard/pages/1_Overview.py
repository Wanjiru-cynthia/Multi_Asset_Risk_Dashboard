"""
Page 1 — Risk Overview
  • Risk heatmap (asset class × risk type, coloured by avg severity)
  • Sentiment trend lines per asset class
  • Live event feed with severity badges
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from data.database import fetch_enriched_events, fetch_heatmap_data, fetch_sentiment_trend
from dashboard.components.charts import (
    render_heatmap,
    render_sentiment_trends,
    severity_badge,
    direction_badge,
    ASSET_LABELS,
    SEV_COLORS,
)
from dashboard.components.macro_sidebar import render_macro_sidebar

st.set_page_config(page_title="Overview | Risk Dashboard", layout="wide", page_icon="📊")
render_macro_sidebar()

# ── page header ───────────────────────────────────────────────────────────────
st.markdown(
    '<h1 style="color:#E63946">📊 Risk Overview</h1>',
    unsafe_allow_html=True,
)

# ── controls ──────────────────────────────────────────────────────────────────
col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 1, 4])
with col_ctrl1:
    lookback_days = st.selectbox("Lookback window", [3, 7, 14, 30], index=1)
with col_ctrl2:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ── data load ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data(days: int):
    return (
        fetch_heatmap_data(),
        fetch_sentiment_trend(days=days),
        fetch_enriched_events(days=days, limit=200),
    )


heatmap_df, trend_df, events_df = load_data(lookback_days)

# ── KPI strip ─────────────────────────────────────────────────────────────────
total_events = len(events_df)
critical_events = len(events_df[events_df["severity"] >= 4]) if not events_df.empty else 0
avg_sev = events_df["severity"].mean() if not events_df.empty and "severity" in events_df.columns else 0
dominant_neg = (
    events_df[events_df["direction"] == "negative"].shape[0]
    if not events_df.empty else 0
)

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Total Events", total_events, help=f"Last {lookback_days} days")
kpi2.metric("Critical / High Severity", critical_events)
kpi3.metric("Avg Severity", f"{avg_sev:.2f}" if avg_sev else "—")
kpi4.metric("Negative-Direction Events", dominant_neg)

st.markdown("<br>", unsafe_allow_html=True)

# ── heatmap + trend ───────────────────────────────────────────────────────────
row1_left, row1_right = st.columns([6, 5])

with row1_left:
    if heatmap_df.empty:
        st.info("No classification data yet. Run `python ingest.py` to populate.")
    else:
        st.plotly_chart(render_heatmap(heatmap_df), use_container_width=True)

with row1_right:
    if trend_df.empty:
        st.info("No sentiment trend data yet.")
    else:
        st.plotly_chart(render_sentiment_trends(trend_df), use_container_width=True)

st.markdown("---")

# ── live event feed ───────────────────────────────────────────────────────────
st.markdown("### 📰 Live Event Feed")

# Filter controls
fc1, fc2, fc3, fc4 = st.columns(4)
with fc1:
    asset_filter = st.multiselect(
        "Asset Class",
        options=["equities", "fixed_income", "fx", "commodities"],
        format_func=lambda x: ASSET_LABELS.get(x, x),
    )
with fc2:
    risk_filter = st.multiselect(
        "Risk Type",
        options=["credit", "market", "geopolitical", "operational", "liquidity"],
        format_func=lambda x: x.title(),
    )
with fc3:
    sev_filter = st.slider("Min Severity", 1, 5, 1)
with fc4:
    dir_filter = st.multiselect("Direction", ["positive", "negative", "neutral"])

# Apply filters
feed = events_df.copy() if not events_df.empty else pd.DataFrame()
if not feed.empty:
    if asset_filter:
        feed = feed[feed["asset_class"].isin(asset_filter)]
    if risk_filter:
        feed = feed[feed["risk_type"].isin(risk_filter)]
    if sev_filter > 1:
        feed = feed[feed["severity"] >= sev_filter]
    if dir_filter:
        feed = feed[feed["direction"].isin(dir_filter)]

if feed.empty:
    st.warning("No events match the current filters.")
else:
    for _, ev in feed.iterrows():
        sev = int(ev.get("severity") or 1)
        border_color = SEV_COLORS.get(sev, "#555")
        pub = str(ev.get("published_at", ""))[:10]
        source = ev.get("source", "Unknown")
        ac = ASSET_LABELS.get(ev.get("asset_class", ""), ev.get("asset_class", "—"))
        rt = str(ev.get("risk_type") or "—").title()
        sent_lbl = str(ev.get("sentiment_label") or "—").title()
        conf = ev.get("sentiment_confidence")
        conf_str = f"{conf:.0%}" if conf else "—"
        url = ev.get("url", "#")

        st.markdown(
            f"""
            <div style="background:#161B22;border-left:4px solid {border_color};
                        padding:12px 16px;margin-bottom:10px;border-radius:4px">
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px">
                {severity_badge(sev)}
                {direction_badge(ev.get("direction"))}
                <span style="color:#888;font-size:0.75rem">{ac} &bull; {rt}</span>
                <span style="color:#555;font-size:0.7rem;margin-left:auto">{source} · {pub}</span>
              </div>
              <a href="{url}" target="_blank" style="color:#C9D1D9;font-size:0.9rem;
                 text-decoration:none;font-weight:500">
                {ev.get('title', '—')}
              </a>
              <div style="margin-top:6px;color:#666;font-size:0.75rem">
                Sentiment: <span style="color:#aaa">{sent_lbl}</span> ({conf_str} confidence)
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
