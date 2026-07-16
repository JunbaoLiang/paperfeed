"""Semantic Scholar enrichment (spec §6.2). Runs daily after ingest.

Refreshes citation_count / citation_velocity for papers published within 180
days and writes citation edges (only between papers already in our table).
"""

import sys
import time
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from packages.core.config import get_settings
from packages.core.db import session_scope
from packages.core.logging import get_logger, log_event
from packages.core.models import Citation, Paper

S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
BATCH_SIZE = 100
FIELDS = "paperId,citationCount,references.paperId,references.externalIds"
REFRESH_WINDOW_DAYS = 180
MAX_RETRIES = 5

logger = get_logger("pipelines.enrich")


def citation_velocity(citation_count: int, published_at: datetime, now: datetime) -> float:
    """citations per month of age; age floored at half a month (spec §6.2)."""
    months = (now - published_at).total_seconds() / (30.44 * 86400)
    return citation_count / max(months, 0.5)


def fetch_batch(client: httpx.Client, arxiv_ids: list[str], api_key: str | None) -> list:
    """POST one batch (≤100 ids) with exponential backoff on 429."""
    headers = {"x-api-key": api_key} if api_key else {}
    payload = {"ids": [f"ARXIV:{aid}" for aid in arxiv_ids]}
    delay = 1.0
    for attempt in range(MAX_RETRIES + 1):
        resp = client.post(S2_BATCH_URL, params={"fields": FIELDS}, json=payload, headers=headers)
        if resp.status_code == 429 and attempt < MAX_RETRIES:
            log_event(logger, "rate_limited", attempt=attempt, sleep=delay)
            time.sleep(delay)
            delay *= 2
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("unreachable")


def main() -> int:
    settings = get_settings()
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=REFRESH_WINDOW_DAYS)

    with session_scope() as session:
        target_ids = list(
            session.scalars(
                select(Paper.arxiv_id)
                .where(Paper.published_at >= cutoff)
                .order_by(Paper.published_at.desc())
            )
        )
        known_ids = set(target_ids) | set(
            session.scalars(select(Paper.arxiv_id).where(Paper.published_at < cutoff))
        )
    log_event(logger, "enrich_start", papers=len(target_ids))

    updated = edges_added = 0
    with httpx.Client(timeout=60.0) as client:
        for i in range(0, len(target_ids), BATCH_SIZE):
            batch = target_ids[i : i + BATCH_SIZE]
            results = fetch_batch(client, batch, settings.s2_api_key)
            with session_scope() as session:
                for arxiv_id, item in zip(batch, results, strict=False):
                    if not item:  # null = S2 doesn't know this paper (yet)
                        continue
                    paper = session.get(Paper, arxiv_id)
                    if paper is None:
                        continue
                    count = item.get("citationCount") or 0
                    paper.s2_paper_id = item.get("paperId")
                    paper.citation_count = count
                    paper.citation_velocity = citation_velocity(count, paper.published_at, now)
                    updated += 1

                    ref_arxiv_ids = {
                        (ref.get("externalIds") or {}).get("ArXiv")
                        for ref in item.get("references") or []
                    }
                    dst_in_corpus = [rid for rid in ref_arxiv_ids if rid and rid in known_ids]
                    if dst_in_corpus:
                        stmt = (
                            pg_insert(Citation)
                            .values([{"src_id": arxiv_id, "dst_id": d} for d in dst_in_corpus])
                            .on_conflict_do_nothing()
                        )
                        # RETURNING gives an exact insert count (rowcount is -1
                        # for multi-row inserts on psycopg3)
                        inserted = session.execute(
                            stmt.returning(Citation.src_id)
                        ).all()
                        edges_added += len(inserted)
            # Politeness: 1 req/s without a key is mandatory; keep it with a key too.
            time.sleep(1.0)

    log_event(logger, "enrich_done", updated=updated, citation_edges_added=edges_added)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("enrich_failed")
        sys.exit(1)
