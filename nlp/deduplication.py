"""
Event deduplication — clusters news articles reporting the same story.
"""

import re
import hashlib
import json
from datetime import datetime, timedelta

STOP_WORDS = {
    'a','an','the','is','are','was','were','be','been','being',
    'have','has','had','do','does','did','will','would','could',
    'should','may','might','shall','in','on','at','to','for','of',
    'and','or','but','with','from','by','as','its','it','this',
    'that','these','those','their','they','we','us','our','after',
    'over','under','amid','says','said','report','reports','new',
    'also','than','more','than','into','about','up','down','out',
}

CLUSTER_WINDOW_HOURS: int = 48
KEY_TOKEN_COUNT: int = 5


def normalize_title(title: str) -> list[str]:
    s = title.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    tokens = [t for t in s.split() if t not in STOP_WORDS and len(t) > 2]
    return tokens


def cluster_key(title: str) -> str:
    tokens = normalize_title(title)
    top = sorted(tokens)[:KEY_TOKEN_COUNT]
    payload = " ".join(top)
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def find_or_create_cluster(
    conn,
    title: str,
    source: str,
    published_at: str,
    window_hours: int = CLUSTER_WINDOW_HOURS,
) -> int:
    key = cluster_key(title)
    cutoff = (
        datetime.fromisoformat(published_at.replace("Z", ""))
        - timedelta(hours=window_hours)
    ).isoformat()

    existing = conn.execute(
        """
        SELECT id, canonical_title, sources_json
        FROM event_clusters
        WHERE cluster_key = ?
          AND last_seen >= ?
        ORDER BY last_seen DESC
        LIMIT 1
        """,
        (key, cutoff),
    ).fetchone()

    if existing:
        cluster_id = existing["id"]
        sources = json.loads(existing["sources_json"] or "[]")
        if source not in sources:
            sources.append(source)
        conn.execute(
            """
            UPDATE event_clusters
            SET last_seen    = MAX(last_seen, ?),
                source_count = (SELECT COUNT(DISTINCT source) FROM news_events WHERE cluster_id = ?),
                sources_json = ?
            WHERE id = ?
            """,
            (published_at, cluster_id, json.dumps(sources), cluster_id),
        )
        return cluster_id

    cur = conn.execute(
        """
        INSERT INTO event_clusters
            (canonical_title, cluster_key, first_seen, last_seen, source_count, sources_json)
        VALUES (?, ?, ?, ?, 1, ?)
        """,
        (title, key, published_at, published_at, json.dumps([source])),
    )
    return cur.lastrowid
