"""
PostgreSQL database layer (Neon) — schema, inserts, and query helpers.
Public API identical to the SQLite version.
"""

import json
import os
import psycopg2
import psycopg2.extras
import pandas as pd
from datetime import datetime, timedelta, timezone


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")


def get_connection():
    url = os.environ["DATABASE_URL"]
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.DictCursor)


def _query_df(sql: str, params: list | None = None) -> pd.DataFrame:
    """Execute a SELECT and return a DataFrame without SQLAlchemy."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or [])
        if cur.description is None:
            return pd.DataFrame()
        cols = [d[0] for d in cur.description]
        rows = [dict(r) for r in cur.fetchall()]
        return pd.DataFrame(rows, columns=cols)
    finally:
        conn.close()


# ── DDL ───────────────────────────────────────────────────────────────────────

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS event_clusters (
        id              SERIAL PRIMARY KEY,
        canonical_title TEXT    NOT NULL,
        cluster_key     TEXT    UNIQUE NOT NULL,
        first_seen      TEXT,
        last_seen       TEXT,
        source_count    INTEGER DEFAULT 1,
        sources_json    TEXT    DEFAULT '[]',
        avg_sentiment   REAL    DEFAULT 0,
        avg_severity    REAL    DEFAULT 0,
        composite_score REAL    DEFAULT 0,
        narrative_label TEXT,
        created_at      TEXT    DEFAULT (NOW()::TEXT)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS news_events (
        id           SERIAL PRIMARY KEY,
        cluster_id   INTEGER REFERENCES event_clusters(id),
        title        TEXT    NOT NULL,
        description  TEXT,
        source       TEXT,
        url          TEXT    UNIQUE,
        published_at TEXT,
        region       TEXT    DEFAULT 'Global',
        fetched_at   TEXT    DEFAULT (NOW()::TEXT)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sentiment_scores (
        id          SERIAL PRIMARY KEY,
        event_id    INTEGER NOT NULL UNIQUE REFERENCES news_events(id) ON DELETE CASCADE,
        positive    REAL    DEFAULT 0,
        negative    REAL    DEFAULT 0,
        neutral     REAL    DEFAULT 0,
        label       TEXT,
        confidence  REAL    DEFAULT 0,
        scored_at   TEXT    DEFAULT (NOW()::TEXT)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_asset_classes (
        id          SERIAL PRIMARY KEY,
        event_id    INTEGER NOT NULL REFERENCES news_events(id) ON DELETE CASCADE,
        cluster_id  INTEGER REFERENCES event_clusters(id),
        asset_class TEXT    NOT NULL,
        confidence  REAL    DEFAULT 1.0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_risk_types (
        id           SERIAL PRIMARY KEY,
        event_id     INTEGER NOT NULL REFERENCES news_events(id) ON DELETE CASCADE,
        cluster_id   INTEGER REFERENCES event_clusters(id),
        risk_type    TEXT    NOT NULL,
        risk_subtype TEXT,
        confidence   REAL    DEFAULT 1.0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS severity_scores (
        id              SERIAL PRIMARY KEY,
        event_id        INTEGER NOT NULL UNIQUE REFERENCES news_events(id) ON DELETE CASCADE,
        severity_index  REAL    DEFAULT 0,
        severity_level  INTEGER DEFAULT 1,
        keyword_score   REAL    DEFAULT 0,
        entity_count    INTEGER DEFAULT 0,
        dollar_impact   INTEGER DEFAULT 0,
        reach_score     REAL    DEFAULT 0,
        direction       TEXT    DEFAULT 'neutral',
        scored_at       TEXT    DEFAULT (NOW()::TEXT)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS narratives (
        id            SERIAL PRIMARY KEY,
        label         TEXT    UNIQUE NOT NULL,
        first_seen    TEXT,
        last_seen     TEXT,
        event_count   INTEGER DEFAULT 0,
        avg_severity  REAL    DEFAULT 0,
        avg_sentiment REAL    DEFAULT 0,
        trend         TEXT    DEFAULT 'stable'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sentiment_event   ON sentiment_scores(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_asset_event       ON event_asset_classes(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_asset_class       ON event_asset_classes(asset_class)",
    "CREATE INDEX IF NOT EXISTS idx_risktype_event    ON event_risk_types(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_risktype_type     ON event_risk_types(risk_type)",
    "CREATE INDEX IF NOT EXISTS idx_severity_event    ON severity_scores(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_cluster_key       ON event_clusters(cluster_key)",
    "CREATE INDEX IF NOT EXISTS idx_cluster_last_seen ON event_clusters(last_seen)",
    "CREATE INDEX IF NOT EXISTS idx_events_cluster    ON news_events(cluster_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_published  ON news_events(published_at)",
    "CREATE INDEX IF NOT EXISTS idx_events_region     ON news_events(region)",
]


def initialize_db() -> None:
    conn = get_connection()
    for stmt in _DDL:
        cur = conn.cursor()
        try:
            cur.execute(stmt)
            conn.commit()
        except Exception:
            conn.rollback()
    conn.close()


def has_data() -> bool:
    try:
        df = _query_df("SELECT COUNT(*) AS n FROM event_clusters")
        return int(df.iloc[0]["n"]) > 0
    except Exception:
        return False


# ── inserts ───────────────────────────────────────────────────────────────────

def insert_event(
    title: str, description: str, source: str, url: str,
    published_at: str, cluster_id: int | None = None, region: str = "Global",
) -> int | None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO news_events (title, description, source, url, published_at, cluster_id, region)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING RETURNING id
            """,
            (title, description, source, url, published_at, cluster_id, region),
        )
        conn.commit()
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def insert_sentiment(event_id: int, positive: float, negative: float,
                     neutral: float, label: str, confidence: float) -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO sentiment_scores (event_id, positive, negative, neutral, label, confidence)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO UPDATE SET
                positive=EXCLUDED.positive, negative=EXCLUDED.negative,
                neutral=EXCLUDED.neutral, label=EXCLUDED.label, confidence=EXCLUDED.confidence
            """,
            (event_id, positive, negative, neutral, label, confidence),
        )
        conn.commit()
    finally:
        conn.close()


def insert_severity(event_id: int, severity_index: float, severity_level: int,
                    keyword_score: float, entity_count: int, dollar_impact: int,
                    reach_score: float, direction: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO severity_scores
                (event_id, severity_index, severity_level, keyword_score,
                 entity_count, dollar_impact, reach_score, direction)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO UPDATE SET
                severity_index=EXCLUDED.severity_index, severity_level=EXCLUDED.severity_level,
                keyword_score=EXCLUDED.keyword_score, entity_count=EXCLUDED.entity_count,
                dollar_impact=EXCLUDED.dollar_impact, reach_score=EXCLUDED.reach_score,
                direction=EXCLUDED.direction
            """,
            (event_id, severity_index, severity_level, keyword_score,
             entity_count, dollar_impact, reach_score, direction),
        )
        conn.commit()
    finally:
        conn.close()


def insert_asset_classes(event_id: int, cluster_id: int | None, asset_classes: list[str]) -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM event_asset_classes WHERE event_id = %s", (event_id,))
        for ac in asset_classes:
            cur.execute(
                "INSERT INTO event_asset_classes (event_id, cluster_id, asset_class) VALUES (%s, %s, %s)",
                (event_id, cluster_id, ac),
            )
        conn.commit()
    finally:
        conn.close()


def insert_risk_types(event_id: int, cluster_id: int | None, risk_types: list[dict]) -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM event_risk_types WHERE event_id = %s", (event_id,))
        for rt in risk_types:
            cur.execute(
                "INSERT INTO event_risk_types (event_id, cluster_id, risk_type, risk_subtype) "
                "VALUES (%s, %s, %s, %s)",
                (event_id, cluster_id, rt["risk_type"], rt.get("risk_subtype")),
            )
        conn.commit()
    finally:
        conn.close()


def update_cluster_scores(cluster_id: int, avg_sentiment: float,
                           avg_severity: float, composite_score: float,
                           narrative_label: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE event_clusters
            SET avg_sentiment=%s, avg_severity=%s, composite_score=%s, narrative_label=%s
            WHERE id=%s
            """,
            (avg_sentiment, avg_severity, composite_score, narrative_label, cluster_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── queries ───────────────────────────────────────────────────────────────────

def fetch_risk_events(
    days: int = 7,
    risk_types: list[str] | None = None,
    asset_classes: list[str] | None = None,
    regions: list[str] | None = None,
    min_severity: int = 1,
    limit: int = 300,
) -> pd.DataFrame:
    try:
        cutoff = _cutoff(days)
        where_clauses = ["c.last_seen >= %s"]
        params: list = [cutoff]

        if risk_types:
            ph = ",".join(["%s"] * len(risk_types))
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM event_risk_types rt2 "
                f"WHERE rt2.cluster_id = c.id AND rt2.risk_type IN ({ph}))"
            )
            params.extend(risk_types)

        if asset_classes:
            ph = ",".join(["%s"] * len(asset_classes))
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM event_asset_classes ac2 "
                f"WHERE ac2.cluster_id = c.id AND ac2.asset_class IN ({ph}))"
            )
            params.extend(asset_classes)

        if regions:
            ph = ",".join(["%s"] * len(regions))
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM news_events ne2 "
                f"WHERE ne2.cluster_id = c.id AND ne2.region IN ({ph}))"
            )
            params.extend(regions)

        if min_severity > 1:
            where_clauses.append(f"c.avg_severity >= {(min_severity - 1) * 20}")

        where_sql = " AND ".join(where_clauses)

        df = _query_df(
            f"""
            SELECT
                c.id              AS cluster_id,
                c.canonical_title AS title,
                c.first_seen, c.last_seen, c.source_count, c.sources_json,
                c.avg_sentiment, c.avg_severity, c.composite_score, c.narrative_label,
                (SELECT e2.url FROM news_events e2
                 WHERE e2.cluster_id = c.id ORDER BY e2.published_at DESC LIMIT 1) AS url,
                (SELECT ARRAY_TO_STRING(ARRAY_AGG(DISTINCT ac.asset_class), ',')
                 FROM event_asset_classes ac WHERE ac.cluster_id = c.id) AS asset_classes,
                (SELECT ARRAY_TO_STRING(ARRAY_AGG(DISTINCT rt.risk_type), ',')
                 FROM event_risk_types rt WHERE rt.cluster_id = c.id) AS risk_types,
                (SELECT ARRAY_TO_STRING(ARRAY_AGG(DISTINCT rt.risk_subtype), ',')
                 FROM event_risk_types rt
                 WHERE rt.cluster_id = c.id AND rt.risk_subtype IS NOT NULL) AS risk_subtypes,
                (SELECT e3.region FROM news_events e3
                 WHERE e3.cluster_id = c.id ORDER BY e3.published_at DESC LIMIT 1) AS region,
                (SELECT sv.direction FROM severity_scores sv
                 JOIN news_events ev ON ev.id = sv.event_id
                 WHERE ev.cluster_id = c.id ORDER BY ev.published_at DESC LIMIT 1) AS direction,
                (SELECT e4.description FROM news_events e4
                 WHERE e4.cluster_id = c.id ORDER BY e4.published_at DESC LIMIT 1) AS description
            FROM event_clusters c
            WHERE {where_sql}
            ORDER BY c.composite_score DESC, c.last_seen DESC
            LIMIT %s
            """,
            params + [limit],
        )
        if not df.empty and "sources_json" in df.columns:
            df["sources_list"] = df["sources_json"].apply(
                lambda x: json.loads(x) if x else []
            )
        return df
    except Exception:
        return pd.DataFrame()


def fetch_heatmap_data(days: int = 7) -> pd.DataFrame:
    try:
        return _query_df(
            """
            SELECT ac.asset_class, rt.risk_type,
                   AVG(sv.severity_index / 20.0) AS avg_severity,
                   COUNT(DISTINCT c.id)           AS event_count
            FROM event_clusters c
            JOIN event_asset_classes ac ON ac.cluster_id = c.id
            JOIN event_risk_types    rt ON rt.cluster_id = c.id
            JOIN news_events          e ON e.cluster_id  = c.id
            JOIN severity_scores     sv ON sv.event_id   = e.id
            WHERE c.last_seen >= %s
            GROUP BY ac.asset_class, rt.risk_type
            """,
            [_cutoff(days)],
        )
    except Exception:
        return pd.DataFrame()


def fetch_sentiment_trend(days: int = 14) -> pd.DataFrame:
    try:
        return _query_df(
            """
            SELECT LEFT(e.published_at, 10) AS date, ac.asset_class,
                   AVG(s.positive - s.negative) AS net_sentiment,
                   AVG(s.positive) AS avg_positive, AVG(s.negative) AS avg_negative,
                   COUNT(DISTINCT c.id) AS event_count
            FROM news_events e
            JOIN event_clusters      c  ON c.id        = e.cluster_id
            JOIN sentiment_scores    s  ON s.event_id  = e.id
            JOIN event_asset_classes ac ON ac.event_id = e.id
            WHERE e.published_at >= %s
            GROUP BY LEFT(e.published_at, 10), ac.asset_class
            ORDER BY date ASC
            """,
            [_cutoff(days)],
        )
    except Exception:
        return pd.DataFrame()


def fetch_composite_trend(days: int = 14) -> pd.DataFrame:
    try:
        return _query_df(
            """
            SELECT LEFT(c.last_seen, 10) AS date, rt.risk_type,
                   AVG(c.composite_score) AS avg_composite,
                   COUNT(DISTINCT c.id)   AS event_count
            FROM event_clusters    c
            JOIN event_risk_types rt ON rt.cluster_id = c.id
            WHERE c.last_seen >= %s
            GROUP BY LEFT(c.last_seen, 10), rt.risk_type
            ORDER BY date ASC
            """,
            [_cutoff(days)],
        )
    except Exception:
        return pd.DataFrame()


def fetch_narrative_stats(days: int = 30) -> pd.DataFrame:
    try:
        return _query_df(
            "SELECT label, event_count, avg_severity, avg_sentiment, "
            "first_seen, last_seen, trend FROM narratives ORDER BY event_count DESC"
        )
    except Exception:
        return pd.DataFrame()


def fetch_cluster_events(cluster_id: int) -> pd.DataFrame:
    try:
        return _query_df(
            """
            SELECT e.id, e.title, e.description, e.source, e.url, e.published_at, e.region,
                   s.positive, s.negative, s.neutral, s.label AS sentiment_label, s.confidence,
                   sv.severity_index, sv.severity_level, sv.direction,
                   sv.keyword_score, sv.entity_count, sv.dollar_impact, sv.reach_score
            FROM news_events e
            LEFT JOIN sentiment_scores s  ON s.event_id  = e.id
            LEFT JOIN severity_scores  sv ON sv.event_id = e.id
            WHERE e.cluster_id = %s
            ORDER BY e.published_at DESC
            """,
            [cluster_id],
        )
    except Exception:
        return pd.DataFrame()


def fetch_enriched_events(days: int = 7, limit: int = 500) -> pd.DataFrame:
    return fetch_risk_events(days=days, limit=limit)


def count_unprocessed_events() -> int:
    try:
        df = _query_df(
            "SELECT COUNT(*) AS n FROM news_events e "
            "WHERE NOT EXISTS (SELECT 1 FROM sentiment_scores s WHERE s.event_id = e.id)"
        )
        return int(df.iloc[0]["n"])
    except Exception:
        return 0
