"""
Master ingestion pipeline.

Usage:
    python ingest.py [--days N]
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest")


def run(days_back: int = 3) -> None:
    from data.database import initialize_db, get_connection
    from data.news_ingestion import fetch_headlines
    from nlp.finbert_pipeline import score_batch
    from nlp.classifier import classify_multi
    from nlp.severity import score_severity
    from nlp.composite_score import compute_composite
    from nlp.narratives import assign_narrative, upsert_narrative
    from nlp.deduplication import find_or_create_cluster

    logger.info("Initialising database …")
    initialize_db()

    logger.info("Fetching headlines (last %d days) …", days_back)
    articles = fetch_headlines(days_back=days_back)
    logger.info("Fetched %d unique articles.", len(articles))

    if not articles:
        logger.info("No articles fetched — check NEWS_API_KEY.")
        return

    # Insert + deduplicate
    new_event_ids: list[int] = []
    conn = get_connection()
    try:
        for art in articles:
            title = (art.get("title") or "").strip()
            if not title or title == "[Removed]":
                continue
            description  = (art.get("description") or "").strip()
            source       = (art.get("source", {}) or {}).get("name", "Unknown")
            url          = art.get("url", "")
            published_at = art.get("publishedAt") or "2000-01-01T00:00:00Z"

            cluster_id = find_or_create_cluster(conn, title, source, published_at)

            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO news_events (title, description, source, url, published_at, cluster_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING RETURNING id
                """,
                (title, description, source, url, published_at, cluster_id),
            )
            row = cur.fetchone()
            if row:
                new_event_ids.append(row[0])

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.info("New events inserted: %d", len(new_event_ids))

    # Fetch unscored
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT e.id, e.title, e.description, e.cluster_id, e.published_at, e.source
        FROM news_events e
        WHERE NOT EXISTS (SELECT 1 FROM sentiment_scores s WHERE s.event_id = e.id)
        ORDER BY e.published_at DESC LIMIT 500
        """
    )
    unscored = cur.fetchall()
    conn.close()

    if not unscored:
        logger.info("No unscored events — done.")
        return

    logger.info("Scoring %d events through NLP pipeline …", len(unscored))
    texts = [f"{r['title']} {r['description'] or ''}".strip() for r in unscored]
    sentiment_results = score_batch(texts)

    conn = get_connection()
    try:
        cluster_aggregates: dict[int, list[dict]] = {}

        for row, text, sent in zip(unscored, texts, sentiment_results):
            event_id   = row["id"]
            cluster_id = row["cluster_id"]
            pub_at     = row["published_at"] or "2000-01-01T00:00:00Z"
            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO sentiment_scores (event_id, positive, negative, neutral, label, confidence)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET
                    positive=EXCLUDED.positive, negative=EXCLUDED.negative,
                    neutral=EXCLUDED.neutral, label=EXCLUDED.label, confidence=EXCLUDED.confidence
                """,
                (event_id, sent.positive, sent.negative, sent.neutral, sent.label, sent.confidence),
            )

            sev = score_severity(text)
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
                (event_id, sev.severity_index, sev.severity_level, sev.keyword_score,
                 sev.entity_count, sev.dollar_impact, sev.reach_score, sev.direction),
            )

            mc = classify_multi(row["title"], row["description"] or "")
            cur.execute("UPDATE news_events SET region=%s WHERE id=%s", (mc["region"], event_id))

            cur.execute("DELETE FROM event_asset_classes WHERE event_id=%s", (event_id,))
            for ac in mc["asset_classes"]:
                cur.execute(
                    "INSERT INTO event_asset_classes (event_id, cluster_id, asset_class) VALUES (%s,%s,%s)",
                    (event_id, cluster_id, ac),
                )

            cur.execute("DELETE FROM event_risk_types WHERE event_id=%s", (event_id,))
            for rt in mc["risk_types"]:
                cur.execute(
                    "INSERT INTO event_risk_types (event_id, cluster_id, risk_type, risk_subtype) VALUES (%s,%s,%s,%s)",
                    (event_id, cluster_id, rt["risk_type"], rt.get("risk_subtype")),
                )

            narrative = assign_narrative(row["title"], row["description"] or "")
            upsert_narrative(conn, narrative, sent.negative, sev.severity_index)

            if cluster_id:
                cluster_aggregates.setdefault(cluster_id, []).append({
                    "neg_sentiment":  sent.negative,
                    "severity_index": sev.severity_index,
                    "published_at":   pub_at,
                    "narrative":      narrative,
                })

        for cluster_id, items in cluster_aggregates.items():
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(DISTINCT source) AS n FROM news_events WHERE cluster_id=%s",
                (cluster_id,),
            )
            source_count = cur.fetchone()[0]
            avg_neg   = sum(i["neg_sentiment"]  for i in items) / len(items)
            avg_sev   = sum(i["severity_index"] for i in items) / len(items)
            latest    = max(items, key=lambda x: x["published_at"])["published_at"]
            narrative = items[-1]["narrative"]
            composite = compute_composite(avg_sev, avg_neg, latest, source_count)

            cur.execute(
                """
                UPDATE event_clusters
                SET avg_sentiment=%s, avg_severity=%s, composite_score=%s,
                    narrative_label=%s, source_count=%s
                WHERE id=%s
                """,
                (avg_neg, avg_sev, composite, narrative, source_count, cluster_id),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.info("Pipeline complete. Scored %d events.", len(unscored))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3)
    args = parser.parse_args()
    run(days_back=args.days)
