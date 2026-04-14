"""
Multi-label risk classifier.

Returns multiple asset classes, multiple risk types with subcategories,
and a region tag. Replaces the old single-label one-to-one classifier.
"""

from __future__ import annotations
from typing import TypedDict


class RiskType(TypedDict):
    risk_type: str
    risk_subtype: str | None
    confidence: float


class MultiClassification(TypedDict):
    asset_classes: list[str]
    risk_types: list[RiskType]
    region: str
    direction: str


# ── hierarchical risk taxonomy ────────────────────────────────────────────────

RISK_TYPE_HIERARCHY: dict[str, dict] = {
    "credit": {
        "keywords": [
            "default", "bankruptcy", "downgrade", "credit rating", "credit spread",
            "high yield", "junk bond", "distressed", "delinquency", "insolvency",
            "debt restructuring", "non-performing", "charge-off", "cds",
            "credit default swap", "moody", "fitch", "s&p rating",
        ],
        "subtypes": {
            "sovereign": ["sovereign debt", "government bond", "imf", "country default"],
            "corporate": ["corporate bond", "company default", "leveraged loan", "hy spread"],
            "consumer": ["consumer credit", "mortgage default", "auto loan", "student debt"],
        },
    },
    "market": {
        "keywords": [
            "crash", "correction", "selloff", "sell-off", "rally", "volatility",
            "vix", "bubble", "drawdown", "bear market", "bull market", "panic",
            "meltdown", "flash crash", "circuit breaker", "risk-off", "market rout",
        ],
        "subtypes": {
            "equity": ["stock crash", "equity selloff", "market crash", "equity market"],
            "rates": ["rate shock", "yield spike", "bond selloff", "duration risk"],
            "volatility": ["vix spike", "vol regime", "implied vol", "realized vol"],
        },
    },
    "geopolitical": {
        "keywords": [
            "war", "conflict", "sanction", "election", "political risk", "government",
            "trade war", "tariff", "geopolitical", "invasion", "coup", "protest",
            "nato", "escalation", "military", "nuclear", "terrorism", "embargo",
        ],
        "subtypes": {
            "war_conflict": ["war", "military strike", "invasion", "ceasefire"],
            "trade": ["trade war", "tariff", "trade embargo", "export ban"],
            "political": ["election", "coup", "government collapse", "political crisis"],
        },
    },
    "operational": {
        "keywords": [
            "fraud", "hack", "cyberattack", "data breach", "outage", "lawsuit",
            "regulatory", "fine", "investigation", "scandal", "recall", "failure",
            "misconduct", "money laundering", "corruption", "sec enforcement",
        ],
        "subtypes": {
            "cyber": ["hack", "cyberattack", "data breach", "ransomware"],
            "regulatory": ["sec fine", "regulatory action", "enforcement", "compliance"],
            "fraud": ["fraud", "misconduct", "money laundering", "corruption"],
        },
    },
    "liquidity": {
        "keywords": [
            "liquidity", "cash crunch", "funding pressure", "repo", "margin call",
            "fire sale", "redemption", "bank run", "illiquid", "liquidity crisis",
            "funding gap", "collateral", "short squeeze", "forced selling",
        ],
        "subtypes": {
            "funding": ["funding gap", "repo market", "credit facility", "funding stress"],
            "market_liquidity": ["bid-ask", "market depth", "fire sale", "illiquid market"],
            "bank": ["bank run", "deposit flight", "bank liquidity", "lender of last resort"],
        },
    },
}

ASSET_CLASS_KEYWORDS: dict[str, list[str]] = {
    "equities": [
        "stock", "equity", "shares", "s&p 500", "nasdaq", "dow jones",
        "russell", "ipo", "earnings", "dividend", "market cap",
        "equity market", "stock market", "nyse", "listed company",
        "growth stock", "value stock",
    ],
    "fixed_income": [
        "bond", "treasury", "yield", "fixed income", "note", "t-bill",
        "duration", "coupon", "maturity", "interest rate", "bund",
        "gilt", "sovereign debt", "municipal bond", "mbs", "investment grade",
        "high yield bond", "spread", "10-year",
    ],
    "fx": [
        "dollar", "euro", "yen", "pound", "currency", "exchange rate",
        "forex", "fx", "dxy", "depreciation", "appreciation", "devaluation",
        "central bank", "monetary policy", "rate hike", "rate cut",
        "fed", "ecb", "boj", "emerging market currency",
    ],
    "commodities": [
        "oil", "gold", "silver", "copper", "crude", "natural gas",
        "commodity", "opec", "energy", "metals", "agriculture",
        "wheat", "corn", "brent", "wti", "precious metals", "lithium",
    ],
}

REGION_KEYWORDS: dict[str, list[str]] = {
    "US": [
        "united states", "federal reserve", "fed", "wall street", "nasdaq",
        "dow jones", "treasury", "sec", "cftc", "american", "us economy",
        "washington", "new york", "u.s.", "american banks",
    ],
    "Europe": [
        "european", "ecb", "eurozone", "germany", "france", "uk",
        "britain", "boe", "ftse", "dax", "euro", "brussels",
        "bank of england", "bundesbank", "italy", "spain",
    ],
    "Asia": [
        "china", "japan", "boj", "nikkei", "hong kong", "singapore",
        "india", "korea", "asian", "yuan", "yen", "pboc",
        "asia pacific", "southeast asia", "emerging asia",
    ],
    "Global": [
        "global", "worldwide", "international", "imf", "world bank",
        "g7", "g20", "opec", "wto", "cross-border", "systemic",
    ],
}

DIRECTION_NEGATIVE = [
    "fall", "decline", "drop", "plunge", "crash", "loss", "down",
    "bearish", "selloff", "slump", "tumble", "deteriorat", "widen",
]
DIRECTION_POSITIVE = [
    "rise", "gain", "rally", "surge", "up", "bullish",
    "recovery", "rebound", "improve", "growth", "tighten",
]

FALLBACK_ASSET_CLASS = "equities"
FALLBACK_RISK_TYPE = "market"
FALLBACK_REGION = "Global"


def _score(text: str, keywords: list[str]) -> int:
    t = text.lower()
    return sum(1 for kw in keywords if kw in t)


def _classify_region(text: str) -> str:
    scores = {region: _score(text, kws) for region, kws in REGION_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else FALLBACK_REGION


def _classify_direction(text: str) -> str:
    neg = _score(text, DIRECTION_NEGATIVE)
    pos = _score(text, DIRECTION_POSITIVE)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def classify_multi(title: str, description: str = "") -> MultiClassification:
    """
    Return multi-label classification: all matching asset classes,
    all matching risk types with subcategories, region, and direction.
    """
    text = f"{title} {description or ''}".strip()

    # Asset classes — all with at least one keyword hit
    asset_classes = [
        ac for ac, kws in ASSET_CLASS_KEYWORDS.items()
        if _score(text, kws) > 0
    ]
    if not asset_classes:
        asset_classes = [FALLBACK_ASSET_CLASS]

    # Risk types — all with at least one keyword hit, with subtype
    risk_types: list[RiskType] = []
    for rtype, data in RISK_TYPE_HIERARCHY.items():
        if _score(text, data["keywords"]) > 0:
            subtype = None
            for sub, sub_kws in data.get("subtypes", {}).items():
                if _score(text, sub_kws) > 0:
                    subtype = sub
                    break
            risk_types.append(RiskType(risk_type=rtype, risk_subtype=subtype, confidence=1.0))

    if not risk_types:
        risk_types = [RiskType(risk_type=FALLBACK_RISK_TYPE, risk_subtype=None, confidence=1.0)]

    return MultiClassification(
        asset_classes=asset_classes,
        risk_types=risk_types,
        region=_classify_region(text),
        direction=_classify_direction(text),
    )


# ── backward-compat shim for ingest.py ───────────────────────────────────────

def classify(title: str, description: str = "") -> dict:
    """Legacy single-label interface used by old ingest path."""
    mc = classify_multi(title, description)
    rt = mc["risk_types"][0]
    from nlp.severity import score_severity
    sev = score_severity(f"{title} {description or ''}")
    return {
        "risk_type":   rt["risk_type"],
        "asset_class": mc["asset_classes"][0],
        "severity":    sev.severity_level,
        "direction":   mc["direction"],
    }
