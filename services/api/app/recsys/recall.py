"""Four-route recall (spec §7 /feed step 1). Target ≈300 deduped candidates.

Exclusions: saved, dismissed, or shown ≥2 times in the last 72h.
Route priority on dedup: vector > graph > fresh > explore.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.core.models import Citation, Feedback, Impression, Paper

VECTOR_LIMIT = 200
GRAPH_LIMIT = 50
FRESH_LIMIT = 50
EXPLORE_LIMIT = 30
VECTOR_WINDOW_DAYS = 30
FRESH_WINDOW_HOURS = 48
EXPLORE_WINDOW_DAYS = 7
OVEREXPOSED_WINDOW_HOURS = 72
OVEREXPOSED_COUNT = 2

# Strong positive signal set used for the graph route (spec §7: 用户强正反馈论文)
STRONG_POSITIVE_EVENTS = ("save", "click_pdf")


@dataclass
class Candidate:
    paper: Paper
    source: str  # 'vector'|'graph'|'fresh'|'explore'
    # graph route: the positive paper this candidate is connected to (for `reason`)
    related_positive_id: str | None = None


def excluded_paper_ids(session: Session, now: datetime) -> set[str]:
    saved_or_dismissed = session.scalars(
        select(Impression.paper_id)
        .join(Feedback, Feedback.impression_id == Impression.impression_id)
        .where(Feedback.event_type.in_(("save", "dismiss")))
        .distinct()
    ).all()
    overexposed = session.scalars(
        select(Impression.paper_id)
        .where(Impression.shown_at >= now - timedelta(hours=OVEREXPOSED_WINDOW_HOURS))
        .group_by(Impression.paper_id)
        .having(func.count() >= OVEREXPOSED_COUNT)
    ).all()
    return set(saved_or_dismissed) | set(overexposed)


def positive_paper_ids(session: Session) -> list[str]:
    return list(
        session.scalars(
            select(Impression.paper_id)
            .join(Feedback, Feedback.impression_id == Impression.impression_id)
            .where(Feedback.event_type.in_(STRONG_POSITIVE_EVENTS))
            .distinct()
        )
    )


def recall_vector(
    session: Session, profile: np.ndarray, excluded: set[str], now: datetime
) -> list[Paper]:
    stmt = (
        select(Paper)
        .where(
            Paper.embedding.is_not(None),
            Paper.published_at >= now - timedelta(days=VECTOR_WINDOW_DAYS),
            Paper.arxiv_id.notin_(excluded) if excluded else True,
        )
        .order_by(Paper.embedding.cosine_distance(profile.tolist()))
        .limit(VECTOR_LIMIT)
    )
    return list(session.scalars(stmt))


def recall_graph(
    session: Session, positives: list[str], excluded: set[str]
) -> list[tuple[Paper, str]]:
    """Papers citing a strong-positive paper, or co-cited with one.

    Returns (paper, related_positive_id) ranked by connection count.
    """
    if not positives:
        return []
    # citing: src cites a positive dst
    citing = session.execute(
        select(Citation.src_id, Citation.dst_id).where(Citation.dst_id.in_(positives))
    ).all()
    # co-cited: some src cites both a positive and the candidate
    c1, c2 = Citation.__table__.alias("c1"), Citation.__table__.alias("c2")
    cocited = session.execute(
        select(c2.c.dst_id, c1.c.dst_id)
        .select_from(c1.join(c2, c1.c.src_id == c2.c.src_id))
        .where(c1.c.dst_id.in_(positives), c2.c.dst_id.notin_(positives))
    ).all()

    counts: dict[str, int] = {}
    related: dict[str, str] = {}
    for cand_id, pos_id in list(citing) + list(cocited):
        if cand_id in excluded or cand_id in positives:
            continue
        counts[cand_id] = counts.get(cand_id, 0) + 1
        related.setdefault(cand_id, pos_id)
    top_ids = sorted(counts, key=counts.get, reverse=True)[:GRAPH_LIMIT]
    if not top_ids:
        return []
    papers = {
        p.arxiv_id: p for p in session.scalars(select(Paper).where(Paper.arxiv_id.in_(top_ids)))
    }
    return [(papers[pid], related[pid]) for pid in top_ids if pid in papers]


def recall_fresh(session: Session, excluded: set[str], now: datetime) -> list[Paper]:
    stmt = (
        select(Paper)
        .where(
            Paper.published_at >= now - timedelta(hours=FRESH_WINDOW_HOURS),
            Paper.arxiv_id.notin_(excluded) if excluded else True,
        )
        .order_by(Paper.citation_velocity.desc().nulls_last())
        .limit(FRESH_LIMIT)
    )
    return list(session.scalars(stmt))


def recall_explore(session: Session, excluded: set[str], now: datetime) -> list[Paper]:
    stmt = (
        select(Paper)
        .where(
            Paper.published_at >= now - timedelta(days=EXPLORE_WINDOW_DAYS),
            Paper.arxiv_id.notin_(excluded) if excluded else True,
        )
        .order_by(func.random())
        .limit(EXPLORE_LIMIT)
    )
    return list(session.scalars(stmt))


def recall_all(
    session: Session, profile: np.ndarray | None, now: datetime | None = None
) -> list[Candidate]:
    now = now or datetime.now(UTC)
    excluded = excluded_paper_ids(session, now)
    positives = positive_paper_ids(session)

    merged: dict[str, Candidate] = {}

    def add(papers, source: str, related: dict[str, str] | None = None):
        for p in papers:
            if p.arxiv_id not in merged:
                merged[p.arxiv_id] = Candidate(
                    paper=p,
                    source=source,
                    related_positive_id=(related or {}).get(p.arxiv_id),
                )

    if profile is not None:
        add(recall_vector(session, profile, excluded, now), "vector")
    graph = recall_graph(session, positives, excluded)
    add([p for p, _ in graph], "graph", {p.arxiv_id: rel for p, rel in graph})
    add(recall_fresh(session, excluded, now), "fresh")
    add(recall_explore(session, excluded, now), "explore")
    return list(merged.values())
