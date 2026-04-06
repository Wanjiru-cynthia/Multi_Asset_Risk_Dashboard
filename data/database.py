"""
SQLite database layer — schema init, insert helpers, and query helpers.
All callers should use get_connection() and close connections promptly.
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "risk_dashboard.db"

DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS news_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    description  TEXT,
    source       TEXT,
    url          TEXT    UNIQUE,
    published_at TEXT,
    fetched_at   TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sentiment_scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    INTEGER NOT NULL REFERENCES news_events(id) ON DELETE CASCADE,
    positive    REAL    DEFAULT 0,
    negative    REAL    DEFAULT 0,
    neutral     REAL    DEFAULT 0,
    label       TEXT,
    confidence  REAL    DEFAULT 0,
    scored_at   TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS risk_classifications (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id       INTEGER NOT NULL REFERENCES news_events(id) ON DELETE CASCADE,
    risk_type      TEXT,
    asset_class    TEXT,
    severity       INTEGER,
    direction      TEXT,
    classified_at  TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_published   ON news_events(published_at);
CREATE INDEX IF NOT EXISTS idx_sentiment_event    ON sentiment_scores(event_id);
CREATE INDEX IF NOT EXISTS idx_classif_event      ON risk_classifications(event_id);
CREATE INDEX IF NOT EXISTS idx_classif_asset      ON risk_classifications(asset_class);
CREATE INDEX IF NOT EXISTS idx_classif_risk       ON risk_classifications(risk_type);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db() -> None:
    conn = get_connection()
    conn.executescript(DDL)
    conn.commit()
    conn.close()


# ── inserts ──────────────────────────────────────────────────────────────────

def insert_event(title: str, description: str, source: str, url: str, published_at: str) -> int | None:
    """Insert a news event; return new row id or None if URL already exists."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO news_events (title, description, source, url, published_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (title, description, source, url, published_at),
        )
        conn.commit()
        return cur.lastrowid if cur.rowcount else None
    finally:
        conn.close()


def insert_sentiment(event_id: int, positive: float, negative: float, neutral: float, label: str, confidence: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO sentiment_scores "
            "(event_id, positive, negative, neutral, label, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, positive, negative, neutral, label, confidence),
        )
        conn.commit()
    finally:
        conn.close()


def insert_classification(event_id: int, risk_type: str, asset_class: str, severity: int, direction: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO risk_classifications "
            "(event_id, risk_type, asset_class, severity, direction) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_id, risk_type, asset_class, severity, direction),
        )
        conn.commit()
    finally:
        conn.close()


# ── queries ───────────────────────────────────────────────────────────────────

def fetch_enriched_events(days: int = 7, limit: int = 500) -> pd.DataFrame:
    """Return events joined with sentiment + classification for the last N days."""
    try:
        conn = get_connection()
        df = pd.read_sql_query(
            """
            SELECT
                e.id,
                e.title,
                e.description,
                e.source,
                e.url,
                e.published_at,
                s.positive,
                s.negative,
                s.neutral,
                s.label      AS sentiment_label,
                s.confidence AS sentiment_confidence,
                c.risk_type,
                c.asset_class,
                c.severity,
                c.direction
            FROM news_events e
            LEFT JOIN sentiment_scores    s ON s.event_id = e.id
            LEFT JOIN risk_classifications c ON c.event_id = e.id
            WHERE e.published_at >= datetime('now', ? )
            ORDER BY e.published_at DESC
            LIMIT ?
            """,
            conn,
            params=(f"-{days} days", limit),
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def fetch_heatmap_data() -> pd.DataFrame:
    """Aggregate avg severity by (asset_class, risk_type) for the heatmap."""
    try:
        conn = get_connection()
        df = pd.read_sql_query(
            """
            SELECT
                c.asset_class,
                c.risk_type,
                AVG(c.severity)        AS avg_severity,
                COUNT(*)               AS event_count
            FROM risk_classifications c
            JOIN news_events e ON e.id = c.event_id
            WHERE e.published_at >= datetime('now', '-7 days')
              AND c.asset_class IS NOT NULL
              AND c.risk_type   IS NOT NULL
            GROUP BY c.asset_class, c.risk_type
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def fetch_sentiment_trend(days: int = 14) -> pd.DataFrame:
    """Daily average sentiment score per asset class for trend lines."""
    try:
        conn = get_connection()
        df = pd.read_sql_query(
            """
            SELECT
                date(e.published_at)          AS date,
                c.asset_class,
                AVG(s.positive - s.negative)  AS net_sentiment,
                AVG(s.positive)               AS avg_positive,
                AVG(s.negative)               AS avg_negative,
                COUNT(*)                      AS event_count
            FROM news_events e
            JOIN sentiment_scores     s ON s.event_id = e.id
            JOIN risk_classifications c ON c.event_id = e.id
            WHERE e.published_at >= datetime('now', ? )
              AND c.asset_class IS NOT NULL
            GROUP BY date(e.published_at), c.asset_class
            ORDER BY date ASC
            """,
            conn,
            params=(f"-{days} days",),
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def fetch_event_by_id(event_id: int) -> pd.DataFrame:
    try:
        conn = get_connection()
        df = pd.read_sql_query(
            """
            SELECT
                e.id, e.title, e.description, e.source, e.url, e.published_at,
                s.positive, s.negative, s.neutral, s.label AS sentiment_label, s.confidence,
                c.risk_type, c.asset_class, c.severity, c.direction
            FROM news_events e
            LEFT JOIN sentiment_scores     s ON s.event_id = e.id
            LEFT JOIN risk_classifications c ON c.event_id = e.id
            WHERE e.id = ?
            """,
            conn,
            params=(event_id,),
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def count_unprocessed_events() -> int:
    try:
        conn = get_connection()
        cur = conn.execute(
            "SELECT COUNT(*) FROM news_events e "
            "WHERE NOT EXISTS (SELECT 1 FROM sentiment_scores s WHERE s.event_id = e.id)"
        )
        n = cur.fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0
