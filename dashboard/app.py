"""
Dashboard entry point.

Uses st.navigation() so this file never appears in the sidebar.
Starts the background scheduler exactly once via @st.cache_resource.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

import streamlit as st

st.set_page_config(
    page_title="Cross-Asset Risk Intelligence",
    page_icon="⚠",
    layout="wide",
)


@st.cache_resource
def _start_scheduler():
    from scheduler import start_scheduler
    return start_scheduler(interval_hours=6)


_start_scheduler()

pg = st.navigation([
    st.Page("pages/1_Risk_Events.py",    title="Risk Events",    icon="⚠"),
    st.Page("pages/2_Risk_Trends.py",    title="Risk Trends",    icon="📈"),
    st.Page("pages/3_Market_Summary.py", title="Market Summary", icon="📊"),
])
pg.run()
