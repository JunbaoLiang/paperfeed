"""Online feature ASSEMBLY: builds UserContext from the DB, then delegates all
feature math to packages/core/features.py (the single implementation — spec §14).
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.core.features import (
    PaperFeatureInput,
    UserContext,
    compute_features,
)
from packages.core.models import Feedback, Impression, Paper, UserProfile
from packages.core.profile import INTERACTION_EVENT_TYPES

POSITIVE_EVENTS = ("save", "external_read", "click_pdf", "click_abstract")
CLICK_EVENTS = ("click_abstract", "click_pdf")
# The "positive library" behind max_sim_saved and reason strings: explicit
# saves plus externally-read papers (spec v1.2).
LIBRARY_EVENTS = ("save", "external_read")
SAVED_EMBEDDINGS_LIMIT = 100


@dataclass
class SavedPaperRef:
    """Saved paper info kept around for `reason` strings (spec §7 step 6)."""

    arxiv_id: str
    title: str
    embedding: np.ndarray | None


@dataclass
class OnlineContext:
    ctx: UserContext
    profile_row: UserProfile
    saved_papers: list[SavedPaperRef] = field(default_factory=list)
    positive_titles: dict[str, str] = field(default_factory=dict)  # arxiv_id -> title
    # Live count from the feedback table. The user_profile.interaction_count
    # column only refreshes nightly (profile_update); reading it online made
    # the cold-start banner lag up to 24h behind the user's real activity.
    interaction_count: int = 0


def load_online_context(session: Session) -> OnlineContext:
    profile_row = session.get(UserProfile, "default")
    if profile_row is None:  # migration seeds it; be defensive anyway
        profile_row = UserProfile(profile_id="default", interaction_count=0)
        session.add(profile_row)

    positive_papers = session.execute(
        select(Paper, Feedback.event_type, Feedback.created_at)
        .join(Impression, Impression.paper_id == Paper.arxiv_id)
        .join(Feedback, Feedback.impression_id == Impression.impression_id)
        .where(Feedback.event_type.in_(POSITIVE_EVENTS))
        .order_by(Feedback.created_at.desc())
    ).all()

    live_interaction_count = int(
        session.scalar(
            select(func.count())
            .select_from(Feedback)
            .where(Feedback.event_type.in_(INTERACTION_EVENT_TYPES))
        )
        or 0
    )

    cat_counter: Counter[str] = Counter()
    author_counter: Counter[str] = Counter()
    saved_papers: list[SavedPaperRef] = []
    clicked_embeddings: list[np.ndarray] = []
    positive_titles: dict[str, str] = {}
    seen_saved: set[str] = set()
    seen_clicked: set[str] = set()

    for paper, event_type, _created in positive_papers:
        cat_counter.update(paper.categories or [])
        author_counter.update(a.get("name", "") for a in (paper.authors or []))
        positive_titles.setdefault(paper.arxiv_id, paper.title)
        if (
            event_type in LIBRARY_EVENTS
            and paper.arxiv_id not in seen_saved
            and len(saved_papers) < SAVED_EMBEDDINGS_LIMIT
        ):
            saved_papers.append(
                SavedPaperRef(
                    arxiv_id=paper.arxiv_id,
                    title=paper.title,
                    embedding=(
                        np.asarray(paper.embedding, dtype=np.float32)
                        if paper.embedding is not None
                        else None
                    ),
                )
            )
            seen_saved.add(paper.arxiv_id)
        if (
            event_type in CLICK_EVENTS
            and paper.arxiv_id not in seen_clicked
            and paper.embedding is not None
            and len(clicked_embeddings) < 5
        ):
            clicked_embeddings.append(np.asarray(paper.embedding, dtype=np.float32))
            seen_clicked.add(paper.arxiv_id)

    profile_emb = (
        np.asarray(profile_row.embedding, dtype=np.float32)
        if profile_row.embedding is not None
        else None
    )
    ctx = UserContext(
        profile_embedding=profile_emb,
        top_categories=[c for c, _ in cat_counter.most_common(5)],
        positive_author_counts=dict(author_counter),
        saved_embeddings=[sp.embedding for sp in saved_papers if sp.embedding is not None],
        last5_clicked_embeddings=clicked_embeddings,
    )
    return OnlineContext(
        ctx=ctx,
        profile_row=profile_row,
        saved_papers=saved_papers,
        positive_titles=positive_titles,
        interaction_count=live_interaction_count,
    )


def paper_feature_input(paper: Paper) -> PaperFeatureInput:
    return PaperFeatureInput(
        embedding=(
            np.asarray(paper.embedding, dtype=np.float32) if paper.embedding is not None else None
        ),
        published_at=paper.published_at,
        citation_count=paper.citation_count,
        citation_velocity=paper.citation_velocity,
        categories=paper.categories or [],
        primary_category=paper.primary_category,
        author_names=[a.get("name", "") for a in (paper.authors or [])],
    )


def compute_candidate_features(
    paper: Paper, ctx: UserContext, recall_source: str, now: datetime
) -> dict[str, float]:
    return compute_features(paper_feature_input(paper), ctx, recall_source, now)
