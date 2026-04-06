"""
NewsAPI ingestion — fetches financial headlines and stores them in SQLite.
"""

import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from newsapi import NewsApiClient

load_dotenv()
logger = logging.getLogger(__name__)

# Financial query terms — broad enough for cross-asset coverage
QUERIES = [
    "financial markets",
    "central bank interest rates",
    "inflation recession",
    "credit default bond",
    "geopolitical risk sanctions",
    "commodity oil gold",
    "currency forex dollar",
    "earnings equity stocks",
]

SOURCES_DOMAINS = (
    "reuters.com,bloomberg.com,ft.com,wsj.com,"
    "cnbc.com,marketwatch.com,investing.com,economist.com"
)


def fetch_headlines(days_back: int = 3, page_size: int = 100) -> list[dict]:
    """
    Fetch headlines from NewsAPI. Returns list of article dicts.
    Deduplicated by URL across queries.
    """
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        raise EnvironmentError("NEWS_API_KEY not set in .env")

    client = NewsApiClient(api_key=api_key)
    seen_urls: set[str] = set()
    articles: list[dict] = []

    for query in QUERIES:
        try:
            response = client.get_everything(
                q=query,
                language="en",
                sort_by="publishedAt",
                page_size=min(page_size, 100),
                domains=SOURCES_DOMAINS,
            )
            for art in response.get("articles", []):
                url = art.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    articles.append(art)
        except Exception as exc:
            logger.warning("NewsAPI query '%s' failed: %s", query, exc)

    logger.info("Fetched %d unique articles from NewsAPI.", len(articles))
    return articles


def ingest(days_back: int = 3) -> int:
    """
    Fetch and store articles. Returns number of new events inserted.
    """
    from data.database import insert_event, initialize_db  # local import to avoid circular

    initialize_db()
    articles = fetch_headlines(days_back=days_back)
    new_count = 0

    for art in articles:
        title = (art.get("title") or "").strip()
        if not title or title == "[Removed]":
            continue

        description = (art.get("description") or "").strip()
        source = (art.get("source", {}) or {}).get("name", "Unknown")
        url = art.get("url", "")
        published_raw = art.get("publishedAt") or datetime.now(timezone.utc).isoformat()

        row_id = insert_event(
            title=title,
            description=description,
            source=source,
            url=url,
            published_at=published_raw,
        )
        if row_id:
            new_count += 1

    logger.info("Inserted %d new events into DB.", new_count)
    return new_count
