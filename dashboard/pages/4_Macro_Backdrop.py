"""
Page 4 — Macro Backdrop Panel
  • Live FRED indicators: VIX, yield curve, credit spreads, DXY, 10Y yield, Fed Funds
  • Historical charts for each series (90-day window)
  • Regime assessment summary
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data.macro_data import fetch_latest_macro, fetch_macro_history, FRED_SERIES
from dashboard.components.charts import render_macro_history
from dashboard.components.macro_sidebar import render_macro_sidebar

st.set_page_config(page_title="Macro Backdrop | Risk Dashboard", layout="wide", page_icon="📡")
render_macro_sidebar()

st.markdown('<h1 style="color:#F4A261">📡 Macro Backdrop</h1>', unsafe_allow_html=True)
st.caption("Live FRED data — VIX · Yield Curve · Credit Spreads · DXY · Fed Funds")

col_ctrl, _ = st.columns([1, 5])
with col_ctrl:
    if st.button("🔄 Refresh FRED Data"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ── load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=900)
def load_macro():
    return fetch_latest_macro()

@st.cache_data(ttl=900)
def load_history():
    return fetch_macro_history(lookback_days=90)

macro = load_macro()
history = load_history()

# ── regime assessment ─────────────────────────────────────────────────────────
def assess_regime(macro_data: dict) -> tuple[str, str, str]:
    """Return (regime_label, colour, description) based on key indicators."""
    vix = (macro_data.get("VIXCLS") or {}).get("value")
    spread = (macro_data.get("T10Y2Y") or {}).get("value")
    hy = (macro_data.get("BAMLH0A0HYM2") or {}).get("value")

    if vix is None:
        return "Unknown", "#888", "Configure FRED_API_KEY to enable regime assessment."

    stress_signals = 0
    if vix > 25:
        stress_signals += 1
    if vix > 35:
        stress_signals += 1
    if spread is not None and spread < 0:
        stress_signals += 2
    if hy is not None and hy > 5.0:
        stress_signals += 1
    if hy is not None and hy > 8.0:
        stress_signals += 1

    if stress_signals >= 4:
        return "RISK-OFF / CRISIS", "#E63946", (
            f"VIX at {vix:.1f} (elevated stress), yield curve at {spread:.2f}%, "
            f"HY spread at {hy:.1f}%. All indicators point to acute risk-off environment."
        )
    elif stress_signals >= 2:
        return "RISK-ELEVATED", "#F4A261", (
            f"VIX at {vix:.1f}, yield curve {spread:.2f if spread else 'N/A'}%, "
            f"HY spread {hy:.1f if hy else 'N/A'}%. Caution warranted."
        )
    else:
        return "RISK-ON / BENIGN", "#2A9D8F", (
            f"VIX at {vix:.1f} (low), yield curve healthy, credit spreads contained."
        )

regime_label, regime_color, regime_desc = assess_regime(macro)

st.markdown(
    f"""
    <div style="background:#161B22;border-left:6px solid {regime_color};
                padding:16px 20px;border-radius:6px;margin-bottom:24px">
      <span style="background:{regime_color};color:#fff;padding:3px 10px;border-radius:4px;
                   font-weight:bold;font-size:0.85rem">{regime_label}</span>
      <p style="color:#C9D1D9;margin:10px 0 0;font-size:0.9rem">{regime_desc}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── live metric cards ─────────────────────────────────────────────────────────
st.markdown("### Current Readings")

DISPLAY_ORDER = [
    ("VIXCLS",        "#E63946", "Equity fear gauge — >25 elevated, >35 crisis"),
    ("T10Y2Y",        "#4CC9F0", "Negative = yield curve inverted (recession signal)"),
    ("BAMLH0A0HYM2",  "#F4A261", "High-yield OAS — >500bps elevated credit risk"),
    ("DTWEXBGS",      "#7209B7", "Broad trade-weighted USD strength index"),
    ("DGS10",         "#4361EE", "Risk-free benchmark rate"),
    ("FEDFUNDS",      "#2A9D8F", "Current Fed policy rate"),
]

metric_cols = st.columns(len(DISPLAY_ORDER))
for col, (sid, color, tooltip) in zip(metric_cols, DISPLAY_ORDER):
    info = macro.get(sid, {})
    val = info.get("value")
    name_short = info.get("name", sid).split("(")[0].split("–")[0].strip()
    date = info.get("date", "—")

    with col:
        if val is not None:
            st.markdown(
                f"""
                <div style="background:#161B22;padding:14px;border-radius:8px;
                            border-top:3px solid {color};text-align:center">
                  <div style="font-size:0.7rem;color:#888;margin-bottom:4px">{name_short}</div>
                  <div style="font-size:1.6rem;font-weight:bold;color:{color}">{val:.2f}</div>
                  <div style="font-size:0.65rem;color:#555;margin-top:4px">{date}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div style="background:#161B22;padding:14px;border-radius:8px;
                            border-top:3px solid #333;text-align:center">
                  <div style="font-size:0.7rem;color:#888;margin-bottom:4px">{name_short}</div>
                  <div style="font-size:1rem;color:#555">N/A</div>
                  <div style="font-size:0.6rem;color:#444">Set FRED_API_KEY</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.markdown("---")

# ── historical charts ─────────────────────────────────────────────────────────
st.markdown("### 90-Day Historical Charts")

CHART_COLORS = {
    "VIXCLS": "#E63946",
    "T10Y2Y": "#4CC9F0",
    "BAMLH0A0HYM2": "#F4A261",
    "DTWEXBGS": "#7209B7",
    "DGS10": "#4361EE",
    "FEDFUNDS": "#2A9D8F",
}

if not history:
    st.info(
        "Historical data unavailable. "
        "Add your FRED API key (free at fred.stlouisfed.org) to `.env` and restart."
    )
else:
    chart_pairs = [DISPLAY_ORDER[i:i+2] for i in range(0, len(DISPLAY_ORDER), 2)]
    for pair in chart_pairs:
        c1, c2 = st.columns(2)
        for col_widget, (sid, color, tooltip) in zip([c1, c2], pair):
            with col_widget:
                if sid in history and not history[sid].empty:
                    series = history[sid]
                    full_name = FRED_SERIES.get(sid, {}).get("name", sid)
                    fig = render_macro_history(series, title=full_name, color=color)
                    # Add reference lines where applicable
                    if sid == "T10Y2Y":
                        fig.add_hline(y=0, line_dash="dash", line_color="#E63946",
                                      line_width=1, annotation_text="Inversion",
                                      annotation_font_color="#E63946")
                    elif sid == "VIXCLS":
                        fig.add_hline(y=25, line_dash="dot", line_color="#F4A261",
                                      line_width=1, annotation_text="Elevated")
                        fig.add_hline(y=35, line_dash="dot", line_color="#E63946",
                                      line_width=1, annotation_text="Crisis")
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption(tooltip)
                else:
                    name_short = FRED_SERIES.get(sid, {}).get("name", sid)
                    st.info(f"No history available for {name_short}")

# ── FRED attribution ──────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Data source: Federal Reserve Bank of St. Louis (FRED). "
    "Series: VIXCLS, T10Y2Y, BAMLH0A0HYM2, DTWEXBGS, DGS10, FEDFUNDS. "
    "All data is subject to FRED terms of use."
)
