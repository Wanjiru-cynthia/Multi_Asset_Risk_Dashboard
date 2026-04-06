"""
Master ingestion script.

Run this to:
  1. Fetch financial headlines from NewsAPI
  2. Score sentiment with FinBERT
  3. Classify risk type, asset class, severity, and direction
  4. Persist everything to SQLite

Usage:
    python ingest.py [--days N]
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest")


def run(days_back: int = 3) -> None:
    from data.database import initialize_db, get_connection, count_unprocessed_events
    from data.news_ingestion import ingest as fetch_news
    from nlp.finbert_pipeline import score_batch
    from nlp.classifier import classify
    from data.database import insert_sentiment, insert_classification

    # 1. Initialise DB schema
    logger.info("Initialising database …")
    initialize_db()

    # 2. Fetch + store news
    logger.info("Fetching news headlines (last %d days) …", days_back)
    new_articles = fetch_news(days_back=days_back)
    logger.info("New articles ingested: %d", new_articles)

    # 3. Find events not yet sentiment-scored
    conn = get_connection()
    unscored = conn.execute(
        """
        SELECT e.id, e.title, e.description
        FROM news_events e
        WHERE NOT EXISTS (SELECT 1 FROM sentiment_scores s WHERE s.event_id = e.id)
        ORDER BY e.published_at DESC
        LIMIT 500
        """
    ).fetchall()
    conn.close()

    if not unscored:
        logger.info("No unscored events — pipeline complete.")
        return

    logger.info("Scoring %d events with FinBERT …", len(unscored))

    ids = [row["id"] for row in unscored]
    texts = [f"{row['title']} {row['description'] or ''}".strip() for row in unscored]

    # 4. Batch sentiment scoring
    sentiment_results = score_batch(texts)

    # 5. Persist sentiment + classification in a single transaction
    conn = get_connection()
    conn.execute("BEGIN")
    try:
        for event_id, text, sent in zip(ids, texts, sentiment_results):
            # Sentiment
            conn.execute(
                "INSERT OR REPLACE INTO sentiment_scores "
                "(event_id, positive, negative, neutral, label, confidence) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (event_id, sent.positive, sent.negative, sent.neutral,
                 sent.label, sent.confidence),
            )
            # Rule-based classification
            row = next((r for r in unscored if r["id"] == event_id), None)
            if row:
                cls = classify(row["title"], row["description"] or "")
                conn.execute(
                    "INSERT OR REPLACE INTO risk_classifications "
                    "(event_id, risk_type, asset_class, severity, direction) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (event_id, cls["risk_type"], cls["asset_class"],
                     cls["severity"], cls["direction"]),
                )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    logger.info("Pipeline complete. Processed %d events.", len(unscored))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Risk dashboard ingestion pipeline")
    parser.add_argument("--days", type=int, default=3, help="Days of news to fetch (default 3)")
    args = parser.parse_args()
    run(days_back=args.days)
