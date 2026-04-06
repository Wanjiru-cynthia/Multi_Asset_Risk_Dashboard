"""
Cross-Asset Risk Intelligence Dashboard
Main entry point — run with: streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

st.set_page_config(
    page_title="Risk Intelligence Dashboard",
    page_icon="⚠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── sidebar navigation header ────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div style="text-align:center;padding:10px 0 5px">
          <span style="font-size:1.8rem">⚠</span><br/>
          <span style="font-size:1.1rem;font-weight:bold;color:#E63946">
            RISK INTELLIGENCE
          </span><br/>
          <span style="font-size:0.7rem;color:#666">Cross-Asset · Live NLP</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")

# ── landing page content ─────────────────────────────────────────────────────
st.markdown(
    """
    <h1 style="color:#E63946;margin-bottom:4px">Cross-Asset Risk Intelligence</h1>
    <p style="color:#888;margin-top:0">
      FinBERT · NewsAPI · yfinance · FRED &nbsp;|&nbsp; Real-time risk classification engine
    </p>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <div style="background:#161B22;padding:20px;border-radius:8px;border-left:4px solid #E63946">
    <h3 style="margin:0 0 8px;color:#E63946">📊 Overview</h3>
    <p style="color:#888;font-size:0.85rem;margin:0">
    Risk heatmap · sentiment trends · live event feed with severity badges
    </p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style="background:#161B22;padding:20px;border-radius:8px;border-left:4px solid #4CC9F0">
    <h3 style="margin:0 0 8px;color:#4CC9F0">🔬 Asset Drilldown</h3>
    <p style="color:#888;font-size:0.85rem;margin:0">
    Per-class price charts · vol metrics · filtered event feed
    </p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div style="background:#161B22;padding:20px;border-radius:8px;border-left:4px solid #2A9D8F">
    <h3 style="margin:0 0 8px;color:#2A9D8F">📋 Event Detail</h3>
    <p style="color:#888;font-size:0.85rem;margin:0">
    Full FinBERT scores · classification breakdown · source metadata
    </p>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div style="background:#161B22;padding:20px;border-radius:8px;border-left:4px solid #F4A261">
    <h3 style="margin:0 0 8px;color:#F4A261">📡 Macro Backdrop</h3>
    <p style="color:#888;font-size:0.85rem;margin:0">
    VIX · yield curve · credit spreads · DXY · Fed Funds — live FRED data
    </p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.info("**Navigate using the pages in the sidebar.** Run `python ingest.py` first to populate the database.")

# ── quick pipeline trigger ───────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Quick Ingestion")
col_a, col_b = st.columns([2, 4])
with col_a:
    days = st.number_input("Days of news to fetch", min_value=1, max_value=7, value=3)
    if st.button("🔄 Run Pipeline Now", type="primary"):
        with st.spinner("Fetching headlines and running FinBERT …"):
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).parent.parent / "ingest.py"),
                     "--days", str(days)],
                    capture_output=True, text=True, timeout=300,
                )
                if result.returncode == 0:
                    st.success("Pipeline complete. Reload the Overview page to see fresh data.")
                    st.code(result.stdout[-2000:] if result.stdout else "Done.")
                else:
                    st.error("Pipeline failed.")
                    st.code(result.stderr[-2000:])
            except Exception as e:
                st.error(f"Could not run pipeline: {e}")

with col_b:
    st.markdown("""
    **Pipeline stages:**
    1. **NewsAPI** — fetches financial headlines across 8 query themes
    2. **FinBERT** (`ProsusAI/finbert`) — scores positive / negative / neutral probability
    3. **Rule Classifier** — assigns risk type, asset class, severity 1–5, direction flag
    4. **SQLite** — persists all results for dashboard queries

    > First run downloads the FinBERT model (~440 MB). Subsequent runs use the local cache.
    """)
