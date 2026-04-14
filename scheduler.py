"""
Background ingestion scheduler.

Runs ingest.py every N hours in a daemon thread so the Streamlit process
keeps data fresh without any manual intervention.

Usage (called once from dashboard/app.py via @st.cache_resource):
    from scheduler import start_scheduler
    sched = start_scheduler(interval_hours=6)
"""

import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

logger = logging.getLogger("scheduler")

PROJECT_ROOT = Path(__file__).parent
INGEST_SCRIPT = PROJECT_ROOT / "ingest.py"

# Shared state written by the job, read by the dashboard
run_log: dict = {
    "last_run_at":   None,   # datetime UTC
    "last_status":   None,   # "success" | "error"
    "last_log_tail": "",
    "run_count":     0,
}


def _run_pipeline() -> None:
    """Subprocess call to ingest.py --days 1 (incremental refresh)."""
    logger.info("Scheduled pipeline starting …")
    try:
        result = subprocess.run(
            [sys.executable, str(INGEST_SCRIPT), "--days", "1"],
            capture_output=True, text=True, timeout=600,
            cwd=str(PROJECT_ROOT),
        )
        run_log["last_run_at"]   = datetime.now(timezone.utc)
        run_log["run_count"]    += 1
        run_log["last_log_tail"] = (result.stdout + result.stderr)[-2000:]

        if result.returncode == 0:
            run_log["last_status"] = "success"
            logger.info("Scheduled pipeline complete.")
        else:
            run_log["last_status"] = "error"
            logger.error("Scheduled pipeline failed:\n%s", result.stderr[-500:])
    except Exception as exc:
        run_log["last_run_at"]   = datetime.now(timezone.utc)
        run_log["last_status"]   = "error"
        run_log["last_log_tail"] = str(exc)
        logger.error("Scheduled pipeline raised: %s", exc)


def _listener(event) -> None:
    if event.exception:
        logger.error("APScheduler job raised an exception.")


def start_scheduler(interval_hours: int = 6) -> BackgroundScheduler:
    """
    Start the background scheduler and return it.
    Call this exactly once via @st.cache_resource so it survives Streamlit reruns.
    The scheduler runs as a daemon thread and stops automatically when the
    Streamlit process exits.
    """
    scheduler = BackgroundScheduler(daemon=True, timezone="UTC")

    scheduler.add_job(
        _run_pipeline,
        trigger="interval",
        hours=interval_hours,
        id="pipeline_refresh",
        name="Ingestion pipeline",
        max_instances=1,          # never overlap runs
        coalesce=True,            # skip missed fires if the job was late
        misfire_grace_time=300,   # 5-min grace window
    )

    scheduler.add_listener(_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    scheduler.start()

    logger.info(
        "Background scheduler started — pipeline runs every %d hour(s).", interval_hours
    )
    return scheduler
