"""
Composite risk score (0–100).

Weights:
  Severity index    40 %
  Sentiment (neg)   30 %
  Recency           20 %   — linear decay over 7 days
  Source count      10 %   — saturates at 5 unique sources
"""

from __future__ import annotations
from datetime import datetime, timezone

WEIGHTS = dict(severity=0.40, sentiment=0.30, recency=0.20, sources=0.10)
RECENCY_DECAY_HOURS = 168  # 7 days
SOURCE_SATURATION = 5


def compute_composite(
    severity_index: float,
    neg_sentiment: float,
    published_at: str,
    source_count: int,
) -> float:
    """Return composite risk score 0–100."""

    # Recency: 100 when fresh, 0 at RECENCY_DECAY_HOURS
    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "")).replace(tzinfo=timezone.utc)
        hours_old = (datetime.now(timezone.utc) - pub).total_seconds() / 3600
    except Exception:
        hours_old = 0.0
    recency = max(0.0, 1.0 - hours_old / RECENCY_DECAY_HOURS) * 100

    source_score = min(source_count / SOURCE_SATURATION, 1.0) * 100

    composite = (
        WEIGHTS["severity"]  * severity_index +
        WEIGHTS["sentiment"] * (neg_sentiment * 100) +
        WEIGHTS["recency"]   * recency +
        WEIGHTS["sources"]   * source_score
    )
    return round(min(100.0, composite), 2)
