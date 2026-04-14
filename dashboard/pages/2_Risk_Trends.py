"""
Page 2 — Risk Trends
  • Composite risk score over time by risk type
  • Sentiment trend lines by asset class
  • Risk heatmap (asset class × risk type)
  • Narrative tracker: recurring themes with counts, severity, sentiment
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from data.database import (
    fetch_heatmap_data, fetch_sentiment_trend,
    fetch_composite_trend, fetch_narrative_stats,
)
from dashboard.components.macro_sidebar import render_macro_sidebar

st.set_page_config(page_title="Risk Trends", page_icon="📈", layout="wide")
render_macro_sidebar()

st.markdown('<h1 style="color:#4CC9F0">📈 Risk Trends</h1>', unsafe_allow_html=True)

ASSET_LABELS = {"equities":"Equities","fixed_income":"Fixed Income",
                "fx":"FX","commodities":"Commodities"}
RISK_COLORS  = {"credit":"#E63946","market":"#F4A261",
                "geopolitical":"#7209B7","operational":"#4CC9F0","liquidity":"#2A9D8F"}
ASSET_COLORS = {"equities":"#4CC9F0","fixed_income":"#4361EE",
                "fx":"#7209B7","commodities":"#F72585"}
SEV_COLORSCALE = [[0,"#1a1a2e"],[0.5,"#F4A261"],[1.0,"#E63946"]]

RISK_TYPES  = ["credit","market","geopolitical","operational","liquidity"]
ASSET_CLASSES = ["equities","fixed_income","fx","commodities"]

# ── controls ──────────────────────────────────────────────────────────────────
ctrl1, ctrl2 = st.columns([2,6])
with ctrl1:
    lookback = st.selectbox("Lookback window", [7,14,30,60], index=1)
with ctrl2:
    if st.button("🔄 Refresh"):
        st.cache_data.clear(); st.rerun()

st.markdown("---")


@st.cache_data(ttl=300)
def load_all(days):
    return (
        fetch_heatmap_data(days=days),
        fetch_sentiment_trend(days=days),
        fetch_composite_trend(days=days),
        fetch_narrative_stats(days=days),
    )

heatmap_df, sentiment_df, composite_df, narrative_df = load_all(lookback)

# ── Section 1: Composite risk trend ──────────────────────────────────────────
st.markdown("### Composite Risk Score — by Risk Type")

if composite_df.empty:
    st.info("No composite trend data yet.")
else:
    fig = go.Figure()
    for rt in RISK_TYPES:
        sub = composite_df[composite_df["risk_type"] == rt].copy()
        if sub.empty:
            continue
        sub["date"] = pd.to_datetime(sub["date"])
        fig.add_trace(go.Scatter(
            x=sub["date"], y=sub["avg_composite"],
            name=rt.title(),
            mode="lines+markers",
            line=dict(color=RISK_COLORS.get(rt,"#888"), width=2),
            marker=dict(size=5),
            hovertemplate=(
                f"<b>{rt.title()}</b><br>"
                "%{x|%b %d}<br>"
                "Composite: %{y:.1f}<extra></extra>"
            ),
        ))
    fig.update_layout(
        yaxis_title="Composite Score (0–100)",
        plot_bgcolor="#0D1117", paper_bgcolor="#0D1117",
        font=dict(color="#C9D1D9", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=320, margin=dict(t=40,b=40,l=60,r=20),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Section 2: Heatmap + Sentiment side by side ───────────────────────────────
col_heat, col_sent = st.columns(2)

with col_heat:
    st.markdown("### Risk Heatmap")
    pivot = pd.DataFrame(0.0, index=ASSET_CLASSES, columns=RISK_TYPES)
    counts = pd.DataFrame(0, index=ASSET_CLASSES, columns=RISK_TYPES)

    if not heatmap_df.empty:
        for _, row in heatmap_df.iterrows():
            ac, rt = row.get("asset_class"), row.get("risk_type")
            if ac in ASSET_CLASSES and rt in RISK_TYPES:
                pivot.at[ac, rt]  = row.get("avg_severity", 0)
                counts.at[ac, rt] = int(row.get("event_count", 0))

    text_matrix = [
        [f"Severity: {pivot.at[ac,rt]:.1f}<br>Events: {counts.at[ac,rt]}"
         for rt in RISK_TYPES]
        for ac in ASSET_CLASSES
    ]
    fig_hm = go.Figure(go.Heatmap(
        z=pivot.values.tolist(),
        x=[r.title() for r in RISK_TYPES],
        y=[ASSET_LABELS.get(a,a) for a in ASSET_CLASSES],
        text=text_matrix,
        hovertemplate="%{y} × %{x}<br>%{text}<extra></extra>",
        colorscale=SEV_COLORSCALE, zmin=0, zmax=5,
        colorbar=dict(title="Severity", thickness=10,
                      tickvals=[1,3,5],ticktext=["Low","Mod","High"]),
    ))
    fig_hm.update_layout(
        plot_bgcolor="#0D1117", paper_bgcolor="#0D1117",
        font=dict(color="#C9D1D9",size=11),
        height=300, margin=dict(t=10,b=40,l=110,r=20),
    )
    st.plotly_chart(fig_hm, use_container_width=True)

with col_sent:
    st.markdown("### Sentiment Trend — by Asset Class")
    if sentiment_df.empty:
        st.info("No sentiment data yet.")
    else:
        fig_s = go.Figure()
        for ac in ASSET_CLASSES:
            sub = sentiment_df[sentiment_df["asset_class"] == ac].copy()
            if sub.empty:
                continue
            sub["date"] = pd.to_datetime(sub["date"])
            fig_s.add_trace(go.Scatter(
                x=sub["date"], y=sub["net_sentiment"],
                name=ASSET_LABELS.get(ac,ac),
                mode="lines+markers",
                line=dict(color=ASSET_COLORS.get(ac,"#888"), width=2),
                marker=dict(size=4),
            ))
        fig_s.add_hline(y=0, line_dash="dash", line_color="#444", line_width=1)
        fig_s.update_layout(
            yaxis_title="Net Sentiment (pos − neg)",
            plot_bgcolor="#0D1117", paper_bgcolor="#0D1117",
            font=dict(color="#C9D1D9",size=11),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=300, margin=dict(t=10,b=40,l=60,r=20),
            hovermode="x unified",
        )
        st.plotly_chart(fig_s, use_container_width=True)

st.markdown("---")

# ── Section 3: Narrative tracker ──────────────────────────────────────────────
st.markdown("### Narrative Tracker — Recurring Themes")

if narrative_df.empty:
    st.info("No narrative data yet.")
else:
    # Bubble chart: x=avg_sentiment(neg), y=avg_severity, size=event_count
    fig_n = go.Figure()
    for _, row in narrative_df.iterrows():
        fig_n.add_trace(go.Scatter(
            x=[float(row.get("avg_sentiment") or 0)],
            y=[float(row.get("avg_severity") or 0)],
            mode="markers+text",
            marker=dict(
                size=max(12, min(60, int(row.get("event_count",1)) * 4)),
                color=float(row.get("avg_severity") or 0),
                colorscale=SEV_COLORSCALE, cmin=0, cmax=100,
                line=dict(color="#30363D", width=1),
            ),
            text=[str(row["label"])],
            textposition="top center",
            textfont=dict(size=9, color="#C9D1D9"),
            name=row["label"],
            showlegend=False,
            hovertemplate=(
                f"<b>{row['label']}</b><br>"
                f"Events: {int(row.get('event_count',0))}<br>"
                f"Avg Severity: {float(row.get('avg_severity',0)):.1f}/100<br>"
                f"Avg Neg Sentiment: {float(row.get('avg_sentiment',0)):.3f}"
                "<extra></extra>"
            ),
        ))

    fig_n.update_layout(
        xaxis_title="Avg Negative Sentiment →",
        yaxis_title="Avg Severity Index (0–100) →",
        plot_bgcolor="#0D1117", paper_bgcolor="#0D1117",
        font=dict(color="#C9D1D9",size=11),
        height=420, margin=dict(t=20,b=50,l=70,r=20),
    )
    st.plotly_chart(fig_n, use_container_width=True)
    st.caption("Bubble size = event count. Top-right = high severity + high negative sentiment.")

    # Table view
    st.markdown("**Narrative Summary Table**")
    tbl = narrative_df[["label","event_count","avg_severity","avg_sentiment",
                         "first_seen","last_seen"]].copy()
    tbl.columns = ["Narrative","Events","Avg Severity (0–100)",
                   "Avg Neg Sentiment","First Seen","Latest"]
    tbl["Avg Severity (0–100)"] = tbl["Avg Severity (0–100)"].round(1)
    tbl["Avg Neg Sentiment"]    = tbl["Avg Neg Sentiment"].round(3)
    tbl["First Seen"] = tbl["First Seen"].str[:10]
    tbl["Latest"]     = tbl["Latest"].str[:10]
    st.dataframe(tbl, use_container_width=True, hide_index=True)
