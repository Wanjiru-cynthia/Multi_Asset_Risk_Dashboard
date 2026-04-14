"""
Quantitative severity scorer — independent of FinBERT sentiment.

Severity index (0–100) is built from four components:
  keyword_score  (0–40): tier of matched intensity keywords
  entity_score   (0–20): breadth of affected entities mentioned
  dollar_score   (0–20): implied dollar/financial scale language
  reach_score    (0–20): geographic/systemic reach indicators

Level mapping (1–5):
  80–100 → 5 CRITICAL
  60–79  → 4 HIGH
  40–59  → 3 MODERATE
  20–39  → 2 WATCH
  0–19   → 1 LOW
"""

from __future__ import annotations
from typing import NamedTuple


class SeverityResult(NamedTuple):
    severity_index: float   # 0–100
    severity_level: int     # 1–5
    keyword_score: float    # 0–40
    entity_count: int
    dollar_impact: int      # 0 or 1
    reach_score: float      # 0–20
    direction: str          # positive | negative | neutral


# ── keyword tiers ─────────────────────────────────────────────────────────────

_TIER4 = [
    "collapse", "crisis", "catastrophe", "meltdown", "contagion",
    "systemic", "emergency", "unprecedented", "panic", "existential",
    "black swan", "total loss", "wipeout",
]
_TIER3 = [
    "plunge", "surge", "tumble", "shock", "severe", "alarm",
    "dramatic", "sharp decline", "sharp drop", "sharp rise",
    "massive", "historic", "record", "extreme",
]
_TIER2 = [
    "concern", "risk", "pressure", "volatile", "uncertainty",
    "decline", "rise", "increase", "decrease", "warn",
    "significant", "major", "notable",
]
_TIER1 = [
    "slight", "modest", "minor", "marginal", "gradual",
    "small", "limited", "cautious",
]

_ENTITY_WORDS = [
    "banks", "firms", "companies", "investors", "markets", "countries",
    "economies", "sectors", "institutions", "governments", "households",
    "consumers", "workers", "funds",
]

_DOLLAR_WORDS = [
    "billion", "trillion", "million", "write-down", "write-off",
    "impairment", "loss", "losses", "bail", "bailout", "rescue",
]

_REACH_WORDS = [
    "global", "worldwide", "systemic", "contagion", "spillover",
    "cross-border", "international", "multi-country", "widespread",
]

_NEG_DIRECTION = [
    "fall", "decline", "drop", "plunge", "crash", "loss", "down",
    "bearish", "selloff", "slump", "tumble", "deteriorat",
]
_POS_DIRECTION = [
    "rise", "gain", "rally", "surge", "up", "bullish",
    "recovery", "rebound", "improve", "growth",
]


def _count(text: str, words: list[str]) -> int:
    t = text.lower()
    return sum(1 for w in words if w in t)


def score_severity(text: str) -> SeverityResult:
    t = text.lower()

    # Keyword score (0–40)
    if _count(t, _TIER4):
        kw = min(40, _count(t, _TIER4) * 20)
    elif _count(t, _TIER3):
        kw = min(30, _count(t, _TIER3) * 15)
    elif _count(t, _TIER2):
        kw = min(20, _count(t, _TIER2) * 8)
    elif _count(t, _TIER1):
        kw = 5
    else:
        kw = 10  # baseline: financial news is inherently noteworthy

    # Entity score (0–20)
    entity_count = _count(t, _ENTITY_WORDS)
    entity_score = min(20, entity_count * 5)

    # Dollar impact (0–20)
    dollar_hit = 1 if _count(t, _DOLLAR_WORDS) else 0
    dollar_score = 20 if dollar_hit else 0

    # Reach score (0–20)
    reach_score = min(20, _count(t, _REACH_WORDS) * 7)

    index = round(kw + entity_score + dollar_score + reach_score, 2)
    index = min(100.0, index)

    if index >= 80:
        level = 5
    elif index >= 60:
        level = 4
    elif index >= 40:
        level = 3
    elif index >= 20:
        level = 2
    else:
        level = 1

    neg = _count(t, _NEG_DIRECTION)
    pos = _count(t, _POS_DIRECTION)
    direction = "negative" if neg > pos else ("positive" if pos > neg else "neutral")

    return SeverityResult(
        severity_index=index,
        severity_level=level,
        keyword_score=float(kw),
        entity_count=entity_count,
        dollar_impact=dollar_hit,
        reach_score=float(reach_score),
        direction=direction,
    )
