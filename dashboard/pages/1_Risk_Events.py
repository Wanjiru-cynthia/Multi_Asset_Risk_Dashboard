"""
Page 1 — Risk Events
  • Filterable event list ranked by composite risk score
  • Source attribution: all outlets, first/latest date
  • Click any event → inline detail drawer with FinBERT scores,
    severity breakdown, probability distribution, article links
"""

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data.database import fetch_risk_events, fetch_cluster_events
from dashboard.components.macro_sidebar import render_macro_sidebar

st.set_page_config(page_title="Risk Events", layout="wide", page_icon="⚠")
render_macro_sidebar()

st.markdown('<h1 style="color:#E63946">⚠ Risk Events</h1>', unsafe_allow_html=True)
st.caption("Deduplicated, multi-classified, composite-scored — ranked by risk significance")

# ── colour maps ───────────────────────────────────────────────────────────────
SEV_COLOR = {1:"#444",2:"#4361EE",3:"#F4A261",4:"#E76F51",5:"#E63946"}
SEV_LABEL = {1:"LOW",2:"WATCH",3:"MOD",4:"HIGH",5:"CRIT"}
DIR_COLOR = {"positive":"#2A9D8F","negative":"#E63946","neutral":"#888"}
ASSET_LABEL = {"equities":"Equities","fixed_income":"Fixed Income",
               "fx":"FX","commodities":"Commodities"}

def sev_badge(level):
    level = max(1, min(5, int(level or 1)))
    return (f'<span style="background:{SEV_COLOR[level]};color:#fff;padding:2px 7px;'
            f'border-radius:4px;font-size:0.7rem;font-weight:bold">{SEV_LABEL[level]}</span>')

def dir_badge(d):
    d = (d or "neutral").lower()
    return (f'<span style="background:{DIR_COLOR.get(d,"#888")};color:#fff;'
            f'padding:2px 7px;border-radius:4px;font-size:0.7rem;font-weight:bold">{d.upper()}</span>')

def score_bar(score, color="#E63946"):
    pct = min(100, max(0, float(score or 0)))
    return (f'<div style="background:#1a1a2e;border-radius:4px;height:6px;width:100%">'
            f'<div style="width:{pct}%;background:{color};height:6px;border-radius:4px"></div></div>'
            f'<span style="font-size:0.7rem;color:#888">{pct:.0f}/100</span>')

# ── filter panel ──────────────────────────────────────────────────────────────
with st.expander("🔍 Filters", expanded=True):
    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    with fc1:
        lookback = st.selectbox("Lookback", [3,7,14,30], index=1, key="ev_lookback")
    with fc2:
        risk_filter = st.multiselect("Risk Type",
            ["credit","market","geopolitical","operational","liquidity"],
            format_func=str.title)
    with fc3:
        asset_filter = st.multiselect("Asset Class",
            ["equities","fixed_income","fx","commodities"],
            format_func=lambda x: ASSET_LABEL.get(x, x))
    with fc4:
        region_filter = st.multiselect("Region", ["US","Europe","Asia","Global"])
    with fc5:
        min_sev = st.slider("Min Severity", 1, 5, 1)
    narrative_filter = st.text_input("Narrative keyword (optional)", "")

col_sort, col_refresh = st.columns([3,1])
with col_sort:
    sort_by = st.radio("Sort by", ["Composite Score","Severity","Latest Date"],
                       horizontal=True)
with col_refresh:
    if st.button("🔄 Refresh"):
        st.cache_data.clear(); st.rerun()

st.markdown("---")

# ── load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_events(days, risk_types, asset_classes, regions, min_severity):
    return fetch_risk_events(
        days=days,
        risk_types=risk_types or None,
        asset_classes=asset_classes or None,
        regions=regions or None,
        min_severity=min_severity,
        limit=300,
    )

events = load_events(lookback, risk_filter, asset_filter, region_filter, min_sev)

if narrative_filter and not events.empty:
    events = events[
        events["narrative_label"].str.contains(narrative_filter, case=False, na=False) |
        events["title"].str.contains(narrative_filter, case=False, na=False)
    ]

# Sort
if not events.empty:
    if sort_by == "Severity":
        events = events.sort_values("avg_severity", ascending=False)
    elif sort_by == "Latest Date":
        events = events.sort_values("last_seen", ascending=False)
    # default: composite_score (already sorted by DB)

# ── KPI strip ─────────────────────────────────────────────────────────────────
k1,k2,k3,k4 = st.columns(4)
k1.metric("Events (deduplicated)", len(events))
k2.metric("Avg Composite Score",
          f"{events['composite_score'].mean():.1f}" if not events.empty else "—")
k3.metric("Critical / High",
          int((events["avg_severity"] >= 60).sum()) if not events.empty else 0)
k4.metric("Negative Direction",
          int((events["direction"] == "negative").sum()) if not events.empty else 0)

st.markdown("---")

# ── selected event state ──────────────────────────────────────────────────────
if "selected_cluster_id" not in st.session_state:
    st.session_state["selected_cluster_id"] = None

# ── event list ────────────────────────────────────────────────────────────────
if events.empty:
    st.info("No events match the current filters. Run the ingestion pipeline to populate data.")
    st.stop()

st.caption(f"Showing {len(events)} deduplicated events")

for _, ev in events.iterrows():
    cluster_id  = ev.get("cluster_id")
    sev_idx     = float(ev.get("avg_severity") or 0)
    sev_level   = max(1, min(5, int(sev_idx / 20) + 1))
    border_col  = SEV_COLOR.get(sev_level, "#444")
    comp_score  = float(ev.get("composite_score") or 0)
    direction   = str(ev.get("direction") or "neutral")
    sources     = ev.get("sources_list") or json.loads(ev.get("sources_json") or "[]")
    src_str     = " · ".join(sources[:4]) + (" …" if len(sources) > 4 else "")
    first_seen  = str(ev.get("first_seen") or "")[:10]
    last_seen   = str(ev.get("last_seen")  or "")[:10]
    narrative   = ev.get("narrative_label") or "—"
    region      = ev.get("region") or "Global"
    risk_types  = (ev.get("risk_types") or "").replace(",", " · ")
    asset_cls   = (ev.get("asset_classes") or "").replace(",", " · ")
    url         = ev.get("url") or "#"
    is_selected = st.session_state["selected_cluster_id"] == cluster_id

    # Card
    col_card, col_btn = st.columns([11, 1])
    with col_card:
        st.markdown(
            f"""
            <div style="background:#161B22;border-left:4px solid {border_col};
                        padding:12px 16px;margin-bottom:6px;border-radius:6px">
              <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px">
                {sev_badge(sev_level)}&nbsp;{dir_badge(direction)}
                <span style="font-size:0.72rem;color:#4CC9F0">⬡ {narrative}</span>
                <span style="font-size:0.7rem;color:#666;margin-left:auto">
                  🌐 {region} &nbsp;|&nbsp; {first_seen} → {last_seen}
                </span>
              </div>
              <div style="font-size:0.92rem;font-weight:600;color:#C9D1D9;margin-bottom:4px">
                {ev.get("title","—")}
              </div>
              <div style="font-size:0.72rem;color:#666;margin-bottom:6px">
                <b>Sources ({len(sources)}):</b> {src_str or "Unknown"}
                &nbsp;|&nbsp; <b>Risk:</b> {risk_types or "—"}
                &nbsp;|&nbsp; <b>Assets:</b> {asset_cls or "—"}
              </div>
              <div style="display:flex;align-items:center;gap:12px">
                <div style="flex:1">{score_bar(comp_score)}</div>
                <span style="font-size:0.7rem;color:#888">Composite</span>
                <span style="font-size:0.7rem;color:#aaa">
                  Sev index: {sev_idx:.0f}/100
                </span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_btn:
        btn_label = "▲ Close" if is_selected else "Detail"
        if st.button(btn_label, key=f"ev_{cluster_id}"):
            if is_selected:
                st.session_state["selected_cluster_id"] = None
            else:
                st.session_state["selected_cluster_id"] = cluster_id
            st.rerun()

    # ── inline detail drawer ──────────────────────────────────────────────────
    if is_selected:
        detail_events = fetch_cluster_events(cluster_id)

        with st.container():
            st.markdown(
                '<div style="background:#0D1117;border:1px solid #30363D;'
                'border-radius:8px;padding:20px;margin-bottom:12px">',
                unsafe_allow_html=True,
            )
            st.markdown(f"#### 📋 Event Detail — {ev.get('title','')[:80]}")

            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Sources", len(sources))
            d2.metric("First Reported", first_seen)
            d3.metric("Latest Update", last_seen)
            d4.metric("Composite Score", f"{comp_score:.1f}/100")

            st.markdown("**Description:**")
            st.markdown(ev.get("description") or "_No description available._")

            if not detail_events.empty:
                # Aggregate sentiment from all cluster events
                avg_pos = detail_events["positive"].mean()
                avg_neg = detail_events["negative"].mean()
                avg_neu = detail_events["neutral"].mean()

                col_sent, col_sev = st.columns(2)

                with col_sent:
                    st.markdown("**FinBERT Sentiment (cluster avg)**")
                    fig = go.Figure(go.Bar(
                        x=["Positive","Negative","Neutral"],
                        y=[round(avg_pos*100,1), round(avg_neg*100,1), round(avg_neu*100,1)],
                        marker_color=["#2A9D8F","#E63946","#F4A261"],
                        text=[f"{v:.1f}%" for v in
                              [avg_pos*100, avg_neg*100, avg_neu*100]],
                        textposition="outside",
                    ))
                    fig.update_layout(
                        yaxis_range=[0,110], height=220,
                        plot_bgcolor="#0D1117", paper_bgcolor="#0D1117",
                        font=dict(color="#C9D1D9",size=11),
                        margin=dict(t=10,b=30,l=30,r=10),
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with col_sev:
                    st.markdown("**Severity Breakdown**")
                    avg_sev_row = detail_events.iloc[0]
                    sev_components = {
                        "Keyword Score": float(avg_sev_row.get("keyword_score") or 0),
                        "Entity Breadth": float(avg_sev_row.get("entity_count") or 0) * 5,
                        "Dollar Impact":  20.0 if avg_sev_row.get("dollar_impact") else 0,
                        "Reach":          float(avg_sev_row.get("reach_score") or 0),
                    }
                    fig2 = go.Figure(go.Bar(
                        x=list(sev_components.keys()),
                        y=list(sev_components.values()),
                        marker_color=["#4CC9F0","#7209B7","#F4A261","#E63946"],
                        text=[f"{v:.0f}" for v in sev_components.values()],
                        textposition="outside",
                    ))
                    fig2.update_layout(
                        yaxis_title="Score (0–40 per component)",
                        yaxis_range=[0,50], height=220,
                        plot_bgcolor="#0D1117", paper_bgcolor="#0D1117",
                        font=dict(color="#C9D1D9",size=11),
                        margin=dict(t=10,b=30,l=30,r=10),
                        showlegend=False,
                    )
                    st.plotly_chart(fig2, use_container_width=True)

                # Source attribution table
                st.markdown("**All Sources**")
                src_rows = detail_events[["source","published_at","url"]].copy()
                src_rows["published_at"] = src_rows["published_at"].str[:16]
                src_rows.columns = ["Source","Published","URL"]
                st.dataframe(src_rows, use_container_width=True, hide_index=True)

            st.markdown("</div>", unsafe_allow_html=True)
