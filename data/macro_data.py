"""
Macro indicator layer — live FRED data via fredapi.
"""

import os
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
logger = logging.getLogger(__name__)

FRED_SERIES: dict[str, dict] = {
    "VIXCLS": {
        "name": "VIX (CBOE Volatility Index)",
        "unit": "index",
        "thresholds": {"low": 15, "elevated": 25, "high": 35},
    },
    "T10Y2Y": {
        "name": "10Y–2Y Treasury Spread (bps)",
        "unit": "percent",
        "thresholds": {"inverted": 0, "flat": 0.5},
    },
    "BAMLH0A0HYM2": {
        "name": "HY Credit Spread (OAS, bps)",
        "unit": "percent",
        "thresholds": {"low": 3.0, "elevated": 5.0, "high": 8.0},
    },
    "DTWEXBGS": {
        "name": "DXY (Broad Trade-Weighted USD)",
        "unit": "index",
        "thresholds": {},
    },
    "DGS10": {
        "name": "10Y Treasury Yield",
        "unit": "percent",
        "thresholds": {},
    },
    "FEDFUNDS": {
        "name": "Fed Funds Rate",
        "unit": "percent",
        "thresholds": {},
    },
}


def _get_fred_client():
    from fredapi import Fred  # noqa: PLC0415
    api_key = os.getenv("FRED_API_KEY", "")
    if not api_key or api_key == "your_fred_api_key_here":
        raise EnvironmentError("FRED_API_KEY not configured in .env")
    return Fred(api_key=api_key)


def fetch_series(series_id: str, lookback_days: int = 90) -> pd.Series:
    """Return a pandas Series for a FRED series over the lookback window."""
    fred = _get_fred_client()
    start = (datetime.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    data = fred.get_series(series_id, observation_start=start)
    return data.dropna()


def fetch_latest_macro() -> dict[str, dict]:
    """
    Return a dict keyed by series_id with the latest value and metadata.
    Gracefully handles individual series failures.
    """
    results: dict[str, dict] = {}
    try:
        fred = _get_fred_client()
    except EnvironmentError as exc:
        logger.warning("FRED client unavailable: %s", exc)
        for sid, meta in FRED_SERIES.items():
            results[sid] = {**meta, "value": None, "date": None, "error": str(exc)}
        return results

    for series_id, meta in FRED_SERIES.items():
        try:
            series = fred.get_series(series_id)
            series = series.dropna()
            latest_val = float(series.iloc[-1])
            latest_date = series.index[-1].strftime("%Y-%m-%d")
            results[series_id] = {
                **meta,
                "value": round(latest_val, 4),
                "date": latest_date,
                "error": None,
            }
        except Exception as exc:
            logger.warning("FRED fetch failed for %s: %s", series_id, exc)
            results[series_id] = {**meta, "value": None, "date": None, "error": str(exc)}
        time.sleep(0.5)

    return results


def fetch_macro_history(lookback_days: int = 90) -> dict[str, pd.Series]:
    """Return historical series for all FRED indicators."""
    results: dict[str, pd.Series] = {}
    try:
        _get_fred_client()
    except EnvironmentError:
        return results

    for series_id in FRED_SERIES:
        try:
            results[series_id] = fetch_series(series_id, lookback_days=lookback_days)
        except Exception as exc:
            logger.warning("History fetch failed for %s: %s", series_id, exc)
        time.sleep(0.5)

    return results
