"""
Narrative / recurring-theme labeler.

Maps a news text to one of a fixed set of thematic narratives using
keyword matching. The best-matching narrative (most keyword hits) is
returned. Falls back to "General Market News" when nothing matches.

Narrative stats (event count, avg severity, avg sentiment) are
maintained in the `narratives` DB table and updated on each ingest run.
"""

from __future__ import annotations

NARRATIVE_PATTERNS: dict[str, list[str]] = {
    "Fed Policy Pivot": [
        "federal reserve", "rate cut", "rate hike", "fed funds",
        "monetary policy", "dovish", "hawkish", "fomc", "powell",
        "quantitative easing", "tightening",
    ],
    "China Economic Slowdown": [
        "china gdp", "china economy", "chinese slowdown", "pboc",
        "yuan", "renminbi", "china trade", "china growth", "li keqiang",
        "china property", "evergrande",
    ],
    "Banking Sector Stress": [
        "bank failure", "regional bank", "bank run", "deposit flight",
        "credit suisse", "silicon valley bank", "svb", "fdic",
        "bank capital", "loan loss", "npl",
    ],
    "Energy Price Shock": [
        "oil price", "crude surge", "energy crisis", "opec",
        "natural gas", "lng", "brent", "wti", "energy supply",
        "oil production", "energy inflation",
    ],
    "Geopolitical Escalation": [
        "war", "military conflict", "sanctions", "nato", "invasion",
        "escalation", "ceasefire", "weapons", "military strike",
        "geopolitical tension", "trade embargo",
    ],
    "Inflation & Rate Path": [
        "inflation", "cpi", "pce", "price pressure", "core inflation",
        "sticky inflation", "disinflation", "deflation", "price index",
        "consumer price",
    ],
    "Credit Market Stress": [
        "credit spread", "high yield", "junk bond", "default",
        "bankruptcy", "distressed debt", "credit risk",
        "leveraged loan", "oas", "credit crunch",
    ],
    "Tech Sector Volatility": [
        "tech selloff", "ai", "semiconductor", "big tech",
        "nasdaq decline", "software", "chip", "nvidia", "apple",
        "microsoft", "meta", "google", "alphabet",
    ],
    "Currency Crisis": [
        "currency crisis", "devaluation", "fx intervention",
        "dollar surge", "emerging market currency", "lira",
        "peso", "rupee", "forex reserves",
    ],
    "Commodity Supercycle": [
        "gold rally", "commodity boom", "copper surge",
        "agricultural price", "food inflation", "wheat", "corn",
        "precious metals", "base metals", "lithium",
    ],
    "Sovereign Debt Risk": [
        "sovereign debt", "government bond", "fiscal deficit",
        "debt ceiling", "imf bailout", "debt restructuring",
        "sovereign default", "public debt",
    ],
    "Housing Market Stress": [
        "housing market", "mortgage rate", "home price",
        "real estate", "property market", "construction",
        "housing bubble", "rent inflation",
    ],
}

FALLBACK_NARRATIVE = "General Market News"


def _score(text: str, keywords: list[str]) -> int:
    t = text.lower()
    return sum(1 for kw in keywords if kw in t)


def assign_narrative(title: str, description: str = "") -> str:
    """Return the best-matching narrative label for the given text."""
    text = f"{title} {description or ''}".lower()
    best_label, best_score = FALLBACK_NARRATIVE, 0
    for label, keywords in NARRATIVE_PATTERNS.items():
        s = _score(text, keywords)
        if s > best_score:
            best_score, best_label = s, label
    return best_label


def upsert_narrative(conn, label: str, sentiment_neg: float, severity_index: float) -> None:
    """Insert or update a narrative row with running stats."""
    existing = conn.execute(
        "SELECT id, event_count, avg_severity, avg_sentiment FROM narratives WHERE label = ?",
        (label,),
    ).fetchone()

    if existing:
        n = existing["event_count"] + 1
        new_sev = ((existing["avg_severity"] * existing["event_count"]) + severity_index) / n
        new_sent = ((existing["avg_sentiment"] * existing["event_count"]) + sentiment_neg) / n
        conn.execute(
            """
            UPDATE narratives
            SET event_count  = ?,
                avg_severity = ?,
                avg_sentiment = ?,
                last_seen    = datetime('now')
            WHERE id = ?
            """,
            (n, round(new_sev, 4), round(new_sent, 4), existing["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO narratives (label, first_seen, last_seen, event_count, avg_severity, avg_sentiment)
            VALUES (?, datetime('now'), datetime('now'), 1, ?, ?)
            """,
            (label, round(severity_index, 4), round(sentiment_neg, 4)),
        )
