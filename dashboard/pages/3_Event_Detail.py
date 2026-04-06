"""
Page 3 — Event Detail View
  • Full FinBERT sentiment output
  • Risk classification breakdown
  • Source metadata
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data.database import fetch_enriched_events, fetch_event_by_id
from dashboard.components.charts import severity_badge, direction_badge, ASSET_LABELS, SEV_COLORS
from dashboard.components.macro_sidebar import render_macro_sidebar

st.set_page_config(page_title="Event Detail | Risk Dashboard", layout="wide", page_icon="📋")
render_macro_sidebar()

st.markdown('<h1 style="color:#2A9D8F">📋 Event Detail View</h1>', unsafe_allow_html=True)


# ── event selector ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_recent_events() -> pd.DataFrame:
    try:
        return fetch_enriched_events(days=14, limit=300)
    except Exception:
        return pd.DataFrame()


events_df = load_recent_events()

if events_df.empty:
    st.warning("No events in the database yet — the pipeline is initialising. Check back in a moment.")
    st.stop()

# If navigated here from drilldown page, pre-select that event
preselect_id = st.session_state.get("selected_event_id", None)

# Build event option list
event_options = {
    row["id"]: f"[{str(row.get('published_at', ''))[:10]}] {row['title'][:90]}"
    for _, row in events_df.iterrows()
}

default_idx = 0
if preselect_id and preselect_id in event_options:
    default_idx = list(event_options.keys()).index(preselect_id)

selected_id = st.selectbox(
    "Select Event",
    options=list(event_options.keys()),
    format_func=lambda x: event_options[x],
    index=default_idx,
)

if selected_id:
    st.session_state["selected_event_id"] = selected_id

st.markdown("---")

# ── load single event ─────────────────────────────────────────────────────────
row = events_df[events_df["id"] == selected_id]
if row.empty:
    st.error("Event not found.")
    st.stop()

ev = row.iloc[0]

# ── header ────────────────────────────────────────────────────────────────────
sev = int(ev.get("severity") or 1)
border_color = SEV_COLORS.get(sev, "#555")

st.markdown(
    f"""
    <div style="background:#161B22;border-left:6px solid {border_color};
                padding:16px 20px;border-radius:6px;margin-bottom:20px">
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px">
        {severity_badge(sev)}&nbsp;{direction_badge(ev.get("direction"))}
        <span style="color:#888;font-size:0.8rem">
          {ASSET_LABELS.get(ev.get("asset_class",""), ev.get("asset_class","—"))}
          &nbsp;&bull;&nbsp;
          {str(ev.get("risk_type","—")).title()} Risk
        </span>
      </div>
      <h3 style="color:#fff;margin:0 0 8px">{ev.get("title","—")}</h3>
      <p style="color:#888;font-size:0.85rem;margin:0">
        {ev.get("description") or "<em>No description available</em>"}
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── metadata strip ────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("Source", ev.get("source", "—"))
m2.metric("Published", str(ev.get("published_at", "—"))[:16])
m3.metric("Event ID", ev.get("id", "—"))
url = ev.get("url", "")
if url:
    m4.markdown(f"[🔗 Open Article]({url})")

st.markdown("---")

# ── sentiment output ──────────────────────────────────────────────────────────
col_sent, col_class = st.columns(2)

with col_sent:
    st.markdown("### 🤖 FinBERT Sentiment")
    pos = ev.get("positive") or 0
    neg = ev.get("negative") or 0
    neu = ev.get("neutral") or 0
    label = str(ev.get("sentiment_label") or "—").title()
    conf = ev.get("sentiment_confidence") or 0

    # Gauge for dominant sentiment
    SENTIMENT_COLORS_MAP = {"Positive": "#2A9D8F", "Negative": "#E63946", "Neutral": "#F4A261"}
    gauge_color = SENTIMENT_COLORS_MAP.get(label, "#888")

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=round(conf * 100, 1),
        title={"text": f"Confidence: {label}", "font": {"color": "#C9D1D9", "size": 16}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#555"},
            "bar": {"color": gauge_color},
            "bgcolor": "#161B22",
            "steps": [
                {"range": [0, 40], "color": "#1a1a2e"},
                {"range": [40, 70], "color": "#16213e"},
                {"range": [70, 100], "color": "#0f3460"},
            ],
        },
        number={"suffix": "%", "font": {"color": gauge_color, "size": 28}},
    ))
    fig_gauge.update_layout(
        paper_bgcolor="#0D1117",
        font={"color": "#C9D1D9"},
        height=220,
        margin=dict(t=40, b=20, l=40, r=40),
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

    # Probability breakdown bar
    fig_bar = go.Figure(go.Bar(
        x=["Positive", "Negative", "Neutral"],
        y=[round(pos * 100, 1), round(neg * 100, 1), round(neu * 100, 1)],
        marker_color=["#2A9D8F", "#E63946", "#F4A261"],
        text=[f"{v:.1f}%" for v in [pos * 100, neg * 100, neu * 100]],
        textposition="outside",
    ))
    fig_bar.update_layout(
        title="Probability Distribution",
        yaxis_title="Probability (%)",
        yaxis_range=[0, 110],
        plot_bgcolor="#0D1117",
        paper_bgcolor="#0D1117",
        font=dict(color="#C9D1D9", size=12),
        height=240,
        margin=dict(t=40, b=30, l=50, r=20),
        showlegend=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_class:
    st.markdown("### 🏷 Risk Classification")

    CLASS_FIELDS = [
        ("Risk Type",   "risk_type",   lambda v: str(v or "—").title()),
        ("Asset Class", "asset_class", lambda v: ASSET_LABELS.get(v, str(v or "—"))),
        ("Severity",    "severity",    lambda v: f"{v}/5" if v else "—"),
        ("Direction",   "direction",   lambda v: str(v or "—").title()),
    ]

    for field_label, field_key, formatter in CLASS_FIELDS:
        val = ev.get(field_key)
        display = formatter(val)
        st.markdown(
            f"""
            <div style="background:#161B22;padding:12px 16px;margin-bottom:8px;
                        border-radius:6px;display:flex;justify-content:space-between">
              <span style="color:#888;font-size:0.85rem">{field_label}</span>
              <span style="color:#C9D1D9;font-weight:bold">{display}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Severity visual scale
    st.markdown("**Severity Scale**")
    sev_fig = go.Figure()
    for s in range(1, 6):
        sev_fig.add_trace(go.Bar(
            x=[s], y=[s],
            marker_color=SEV_COLORS[s],
            opacity=1.0 if s == sev else 0.3,
            showlegend=False,
            hovertemplate=f"Severity {s}<extra></extra>",
            width=0.6,
        ))
    sev_fig.update_layout(
        xaxis=dict(tickvals=[1, 2, 3, 4, 5],
                   ticktext=["1 Low", "2 Watch", "3 Mod", "4 High", "5 Crit"],
                   tickfont=dict(color="#C9D1D9")),
        yaxis_visible=False,
        barmode="overlay",
        plot_bgcolor="#0D1117",
        paper_bgcolor="#0D1117",
        height=140,
        margin=dict(t=10, b=40, l=10, r=10),
    )
    st.plotly_chart(sev_fig, use_container_width=True)

st.markdown("---")

# ── similar events ────────────────────────────────────────────────────────────
st.markdown("### 🔗 Similar Events (same asset class + risk type)")

similar = events_df[
    (events_df["asset_class"] == ev.get("asset_class"))
    & (events_df["risk_type"] == ev.get("risk_type"))
    & (events_df["id"] != selected_id)
].head(5)

if similar.empty:
    st.caption("No similar events found in the current window.")
else:
    for _, s_ev in similar.iterrows():
        s_sev = int(s_ev.get("severity") or 1)
        s_border = SEV_COLORS.get(s_sev, "#555")
        st.markdown(
            f"""
            <div style="background:#161B22;border-left:3px solid {s_border};
                        padding:8px 12px;margin-bottom:6px;border-radius:4px">
              {severity_badge(s_sev)}&nbsp;
              <a href="{s_ev.get("url","#")}" target="_blank"
                 style="color:#C9D1D9;font-size:0.85rem;text-decoration:none">
                {s_ev.get("title","—")[:100]}
              </a>
              <span style="color:#555;font-size:0.7rem;float:right">
                {str(s_ev.get("published_at",""))[:10]}
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
