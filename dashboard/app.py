"""
Cross-Asset Risk Intelligence Dashboard — landing page + scheduler bootstrap.
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

# ── background scheduler ──────────────────────────────────────────────────────
# @st.cache_resource ensures the scheduler is created exactly once per
# Streamlit server process — it survives page switches and reruns.

@st.cache_resource
def _start_scheduler():
    from scheduler import start_scheduler
    return start_scheduler(interval_hours=6)

_sched = _start_scheduler()

# ── page header ───────────────────────────────────────────────────────────────
st.title("Cross-Asset Risk Intelligence")
st.markdown(
    "Real-time financial news · **FinBERT** sentiment · quantitative severity · "
    "composite risk scoring across equities, fixed income, FX, and commodities."
)

st.markdown("---")

# ── navigation links ──────────────────────────────────────────────────────────
st.markdown("### Navigate")
col1, col2, col3 = st.columns(3)

with col1:
    st.page_link("pages/1_Risk_Events.py",    label="Risk Events",    icon="⚠")
    st.caption("Deduplicated event list · composite scores · inline detail")

with col2:
    st.page_link("pages/2_Risk_Trends.py",    label="Risk Trends",    icon="📈")
    st.caption("Composite trend · heatmap · sentiment · narrative tracker")

with col3:
    st.page_link("pages/3_Market_Summary.py", label="Market Summary", icon="📊")
    st.caption("Live quotes · price charts · FRED macro indicators")

st.markdown("---")

# ── scheduler status panel ────────────────────────────────────────────────────
st.markdown("### Pipeline Scheduler")

from scheduler import run_log
from datetime import datetime, timezone

next_job   = _sched.get_job("pipeline_refresh")
next_run   = next_job.next_run_time if next_job else None
last_run   = run_log["last_run_at"]
last_status = run_log["last_status"]
run_count  = run_log["run_count"]

s1, s2, s3, s4 = st.columns(4)
s1.metric("Schedule", "Every 6 hours")
s2.metric("Runs this session", run_count)
s3.metric(
    "Last run",
    last_run.strftime("%H:%M UTC") if last_run else "Not yet",
)
s4.metric(
    "Next run",
    next_run.strftime("%H:%M UTC") if next_run else "—",
)

# Status badge
if last_status == "success":
    st.success("Last scheduled run completed successfully.")
elif last_status == "error":
    st.error("Last scheduled run failed — see log below.")
    if run_log["last_log_tail"]:
        with st.expander("Error log"):
            st.code(run_log["last_log_tail"])
else:
    st.info(
        "Scheduler is running. The pipeline will execute automatically every 6 hours. "
        "Use the manual trigger below to run immediately."
    )

st.markdown("---")

# ── manual trigger ─────────────────────────────────────────────────────────────
st.markdown("### Manual Pipeline Trigger")
col_a, col_b = st.columns([2, 4])

with col_a:
    days = st.number_input("Days of news to fetch", min_value=1, max_value=7, value=3)
    if st.button("🔄 Run Pipeline Now", type="primary"):
        with st.spinner("Fetching headlines and running FinBERT …"):
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable,
                     str(Path(__file__).parent.parent / "ingest.py"),
                     "--days", str(days)],
                    capture_output=True, text=True, timeout=600,
                    cwd=str(Path(__file__).parent.parent),
                )
                if result.returncode == 0:
                    st.success("Pipeline complete. Navigate to Risk Events to see fresh data.")
                    st.code(result.stdout[-2000:] if result.stdout else "Done.")
                else:
                    st.error("Pipeline failed.")
                    st.code(result.stderr[-2000:])
            except Exception as exc:
                st.error(f"Could not run pipeline: {exc}")

with col_b:
    st.markdown("""
    **Automated schedule:** every 6 hours (incremental, `--days 1`)

    **Manual run:** fetches the selected number of days, useful after a long gap or first deployment.

    **Pipeline stages:**
    1. **NewsAPI** — headlines across 8 financial query themes
    2. **Deduplication** — clusters same-story articles across sources (48-hour window)
    3. **FinBERT** — positive / negative / neutral probability per article
    4. **Severity scorer** — independent 0–100 index (keywords, entities, dollar impact, reach)
    5. **Multi-classifier** — asset classes[], risk types[] with subcategories, region, direction
    6. **Narrative labeler** — assigns recurring theme (Fed Policy Pivot, Energy Shock, etc.)
    7. **Composite scorer** — weighted rank: severity 40%, sentiment 30%, recency 20%, sources 10%
    8. **SQLite** — persists all results; dashboard queries are read-only
    """)

st.caption(
    "⚠ On Streamlit Cloud the scheduler runs while the app is active. "
    "If the app sleeps due to inactivity, the scheduler pauses and resumes on next visit."
)
