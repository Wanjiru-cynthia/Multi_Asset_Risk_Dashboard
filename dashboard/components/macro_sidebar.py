"""
Macro backdrop sidebar — rendered on every page.
Shows live FRED indicators in a compact format.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

import streamlit as st
from data.macro_data import fetch_latest_macro


@st.cache_resource
def _start_scheduler():
    from scheduler import start_scheduler
    return start_scheduler(interval_hours=6)

_start_scheduler()


def _indicator_color(series_id: str, value: float | None) -> str:
    """Return a hex colour for the metric delta based on risk signal."""
    if value is None:
        return "#888888"
    if series_id == "VIXCLS":
        if value >= 35:
            return "#E63946"
        if value >= 25:
            return "#F4A261"
        return "#2A9D8F"
    if series_id == "T10Y2Y":
        return "#E63946" if value < 0 else ("#F4A261" if value < 0.5 else "#2A9D8F")
    if series_id == "BAMLH0A0HYM2":
        if value >= 8:
            return "#E63946"
        if value >= 5:
            return "#F4A261"
        return "#2A9D8F"
    return "#C9D1D9"


@st.cache_data(ttl=900)  # refresh every 15 min
def _load_macro() -> dict:
    return fetch_latest_macro()


def render_macro_sidebar() -> None:
    """Call this from any page to render the macro panel in st.sidebar."""
    st.markdown(
        "<style>[data-testid='stSidebarNav'] li:first-child{display:none!important}</style>",
        unsafe_allow_html=True,
    )

    # Show a visible error if DATABASE_URL is missing
    import os
    if not os.environ.get("DATABASE_URL"):
        st.error("DATABASE_URL not set — add it to Streamlit Cloud secrets.", icon="🔴")

    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📡 Macro Backdrop")
        st.caption("FRED live indicators · refreshes every 15 min")

        macro = _load_macro()

        DISPLAY_ORDER = ["VIXCLS", "T10Y2Y", "BAMLH0A0HYM2", "DTWEXBGS", "DGS10", "FEDFUNDS"]

        for sid in DISPLAY_ORDER:
            info = macro.get(sid, {})
            val = info.get("value")
            name = info.get("name", sid)
            date = info.get("date", "—")
            unit = info.get("unit", "")
            error = info.get("error")

            label = name.split("(")[0].strip()
            if val is not None:
                display = f"{val:.2f}"
                color = _indicator_color(sid, val)
                st.markdown(
                    f"""
                    <div style="margin-bottom:10px">
                      <span style="font-size:0.75rem;color:#888">{label}</span><br/>
                      <span style="font-size:1.1rem;font-weight:bold;color:{color}">{display}</span>
                      <span style="font-size:0.7rem;color:#666"> {unit}</span><br/>
                      <span style="font-size:0.65rem;color:#555">{date}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div style="margin-bottom:10px">
                      <span style="font-size:0.75rem;color:#888">{label}</span><br/>
                      <span style="font-size:0.85rem;color:#555">N/A — configure FRED_API_KEY</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("---")
