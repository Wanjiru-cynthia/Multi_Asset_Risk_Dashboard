"""
Rule-based risk classifier.

Given a news headline (+ optional description), returns:
    risk_type   : credit | market | geopolitical | operational | liquidity
    asset_class : equities | fixed_income | fx | commodities
    severity    : 1–5
    direction   : positive | negative | neutral
"""

import re
from typing import TypedDict


class Classification(TypedDict):
    risk_type: str
    asset_class: str
    severity: int
    direction: str


# ── keyword maps ──────────────────────────────────────────────────────────────

RISK_TYPE_KEYWORDS: dict[str, list[str]] = {
    "credit": [
        "default", "bankruptcy", "downgrade", "credit rating", "credit spread",
        "high yield", "junk bond", "distressed", "delinquency", "insolvency",
        "debt restructuring", "non-performing", "charge-off", "credit risk",
        "cds", "credit default swap", "moody", "s&p rating", "fitch",
    ],
    "market": [
        "crash", "correction", "selloff", "sell-off", "rally", "volatility", "vix",
        "bubble", "drawdown", "bear market", "bull market", "panic", "meltdown",
        "circuit breaker", "flash crash", "market crash", "equity sell", "risk-off",
        "risk off", "market turmoil", "market stress", "market rout",
    ],
    "geopolitical": [
        "war", "conflict", "sanction", "election", "political risk", "government",
        "trade war", "tariff", "geopolitical", "invasion", "coup", "protest",
        "nato", "escalation", "military", "nuclear", "terrorism", "embargo",
        "diplomatic", "sovereignty", "regime", "referendum",
    ],
    "operational": [
        "fraud", "hack", "cyberattack", "data breach", "outage", "lawsuit",
        "regulatory", "fine", "investigation", "scandal", "recall", "failure",
        "misconduct", "money laundering", "corruption", "cftc", "sec enforcement",
        "doj", "class action", "breach", "system failure",
    ],
    "liquidity": [
        "liquidity", "cash crunch", "funding pressure", "repo", "margin call",
        "fire sale", "redemption", "bank run", "illiquid", "liquidity crisis",
        "funding gap", "collateral", "short squeeze", "forced selling",
        "liquidity squeeze", "credit facility", "line of credit",
    ],
}

ASSET_CLASS_KEYWORDS: dict[str, list[str]] = {
    "equities": [
        "stock", "equity", "shares", "s&p 500", "s&p500", "nasdaq", "dow jones",
        "russell", "ipo", "earnings", "dividend", "market cap", "tech stocks",
        "growth stock", "value stock", "equity market", "stock market",
        "listed company", "nyse", "nyse:", "nyse amex",
    ],
    "fixed_income": [
        "bond", "treasury", "yield", "fixed income", "note", "t-bill",
        "duration", "coupon", "maturity", "interest rate", "bund",
        "gilt", "sovereign debt", "municipal bond", "mbs", "abs",
        "investment grade", "high yield bond", "spread", "10-year",
    ],
    "fx": [
        "dollar", "euro", "yen", "pound", "currency", "exchange rate",
        "forex", "fx", "dxy", "depreciation", "appreciation", "devaluation",
        "central bank", "monetary policy", "rate hike", "rate cut",
        "fed", "ecb", "boj", "bank of england", "rba", "emerging market currency",
    ],
    "commodities": [
        "oil", "gold", "silver", "copper", "crude", "natural gas",
        "commodity", "opec", "energy", "metals", "agriculture", "wheat",
        "corn", "soybean", "brent", "wti", "precious metals", "base metals",
        "lithium", "uranium", "coal", "lng",
    ],
}

# Severity scoring: weight × keyword list
SEVERITY_TIERS: list[tuple[int, list[str]]] = [
    (5, [
        "collapse", "crisis", "catastrophe", "disaster", "panic", "meltdown",
        "contagion", "systemic risk", "emergency", "existential", "catastrophic",
        "unprecedented", "black swan", "total loss",
    ]),
    (4, [
        "surge", "plunge", "tumble", "soar", "spike", "slump",
        "warning", "alarm", "severe", "shock", "major", "significant",
        "dramatic", "sharp decline", "sharp rise", "sharp drop",
    ]),
    (3, [
        "rise", "fall", "increase", "decrease", "concern", "risk",
        "threat", "pressure", "uncertainty", "volatile", "weaker",
        "stronger", "mixed", "turbulence",
    ]),
    (2, [
        "slight", "modest", "minor", "limited", "marginal", "small",
        "gradual", "cautious", "stable but",
    ]),
    (1, []),  # default baseline
]

DIRECTION_NEGATIVE: list[str] = [
    "fall", "decline", "drop", "plunge", "crash", "loss", "negative",
    "down", "bearish", "risk", "concern", "warning", "sell", "weak",
    "slump", "tumble", "deteriorat", "worsening", "selloff",
]

DIRECTION_POSITIVE: list[str] = [
    "rise", "gain", "rally", "surge", "growth", "positive", "up",
    "bullish", "recovery", "improvement", "strong", "beat", "outperform",
    "record high", "rebound", "uptick",
]

FALLBACK_RISK_TYPE = "market"
FALLBACK_ASSET_CLASS = "equities"


def _score_text(text: str, keyword_list: list[str]) -> int:
    """Count how many keywords appear in lowercased text."""
    text_lower = text.lower()
    return sum(1 for kw in keyword_list if kw in text_lower)


def _classify_risk_type(text: str) -> str:
    scores = {rtype: _score_text(text, kws) for rtype, kws in RISK_TYPE_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else FALLBACK_RISK_TYPE


def _classify_asset_class(text: str) -> str:
    scores = {ac: _score_text(text, kws) for ac, kws in ASSET_CLASS_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else FALLBACK_ASSET_CLASS


def _classify_severity(text: str) -> int:
    for severity, keywords in SEVERITY_TIERS:
        if _score_text(text, keywords) > 0:
            return severity
    return 2  # baseline for any financial news


def _classify_direction(text: str) -> str:
    neg = _score_text(text, DIRECTION_NEGATIVE)
    pos = _score_text(text, DIRECTION_POSITIVE)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def classify(title: str, description: str = "") -> Classification:
    """Main entry point. Accepts headline + optional description."""
    text = f"{title} {description or ''}".strip()
    return Classification(
        risk_type=_classify_risk_type(text),
        asset_class=_classify_asset_class(text),
        severity=_classify_severity(text),
        direction=_classify_direction(text),
    )
