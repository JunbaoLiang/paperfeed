"""arXiv ingestion (spec §6.1). Idempotent daily job: `python -m pipelines.ingest`.

Pulls the last 3 days of papers for configured categories via the arXiv API,
paginated 100/page with ≥3s between requests (arXiv politeness rule). Sorted by
lastUpdatedDate so revised versions (v2+) are caught as well as new papers.
"""

import sys
import time
from datetime import UTC, datetime, timedelta

import httpx

# Parsing helpers moved to packages/core/arxiv.py (shared with the online
# API's /external-read); re-exported here so callers/tests keep working.
from packages.core.arxiv import (
    ARXIV_API,
    clean_abstract,  # noqa: F401 (re-export)
    parse_entry,
    split_arxiv_id,  # noqa: F401 (re-export)
)
from packages.core.config import get_settings
from packages.core.db import session_scope
from packages.core.logging import get_logger, log_event
from packages.core.models import Paper

PAGE_SIZE = 100
REQUEST_INTERVAL_S = 3.0
WINDOW_DAYS = 3

logger = get_logger("pipelines.ingest")


def fetch_recent_entries(categories: list[str], window_days: int = WINDOW_DAYS) -> list[dict]:
    """Page through the API until entries are older than the window."""
    import feedparser

    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    search_query = " OR ".join(f"cat:{c}" for c in categories)
    collected: list[dict] = []
    start = 0
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        while True:
            resp = client.get(
                ARXIV_API,
                params={
                    "search_query": search_query,
                    "start": start,
                    "max_results": PAGE_SIZE,
                    "sortBy": "lastUpdatedDate",
                    "sortOrder": "descending",
                },
            )
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            entries = feed.entries
            if not entries:
                break
            page = [parse_entry(e) for e in entries]
            collected.extend(p for p in page if p["arxiv_updated_at"] >= cutoff)
            oldest = min(p["arxiv_updated_at"] for p in page)
            log_event(logger, "page_fetched", start=start, count=len(entries), oldest=oldest)
            if oldest < cutoff:
                break
            start += PAGE_SIZE
            time.sleep(REQUEST_INTERVAL_S)
    return collected


def upsert_papers(rows: list[dict]) -> dict[str, int]:
    """UPSERT by arxiv_id. A newer arxiv_updated_at bumps latest_version and
    clears the embedding so embed.py re-vectorizes (spec §6.1)."""
    inserted = updated = unchanged = 0
    # Dedup within the batch (same id can appear once per page overlap): keep newest.
    by_id: dict[str, dict] = {}
    for r in rows:
        cur = by_id.get(r["arxiv_id"])
        if cur is None or r["arxiv_updated_at"] > cur["arxiv_updated_at"]:
            by_id[r["arxiv_id"]] = r

    with session_scope() as session:
        for r in by_id.values():
            existing = session.get(Paper, r["arxiv_id"])
            if existing is None:
                session.add(
                    Paper(
                        arxiv_id=r["arxiv_id"],
                        latest_version=r["version"],
                        title=r["title"],
                        abstract=r["abstract"],
                        authors=r["authors"],
                        categories=r["categories"],
                        primary_category=r["primary_category"],
                        published_at=r["published_at"],
                        arxiv_updated_at=r["arxiv_updated_at"],
                        pdf_url=r["pdf_url"],
                    )
                )
                inserted += 1
            elif r["arxiv_updated_at"] > existing.arxiv_updated_at:
                existing.title = r["title"]
                existing.abstract = r["abstract"]
                existing.authors = r["authors"]
                existing.categories = r["categories"]
                existing.primary_category = r["primary_category"]
                existing.arxiv_updated_at = r["arxiv_updated_at"]
                existing.pdf_url = r["pdf_url"]
                existing.latest_version = existing.latest_version + 1
                existing.embedding = None  # trigger re-embedding
                existing.embedding_model = None
                updated += 1
            else:
                unchanged += 1
    return {"inserted": inserted, "updated": updated, "unchanged": unchanged}


def main() -> int:
    settings = get_settings()
    cats = settings.arxiv_category_list
    log_event(logger, "ingest_start", categories=cats)
    entries = fetch_recent_entries(cats)
    stats = upsert_papers(entries)
    log_event(logger, "ingest_done", fetched=len(entries), **stats)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("ingest_failed")
        sys.exit(1)
