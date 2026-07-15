"""GET /feed, /saved, /stats (spec §7)."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.core.features import cosine
from packages.core.models import (
    Feedback,
    Impression,
    MetricsDaily,
    ModelRegistry,
    Paper,
    UserProfile,
)
from services.api.app.deps import DbSession
from services.api.app.recsys.features import (
    OnlineContext,
    compute_candidate_features,
    load_online_context,
)
from services.api.app.recsys.interleave import ARM_CHALLENGER, team_draft
from services.api.app.recsys.recall import (
    Candidate,
    excluded_paper_ids,
    recall_all,
    recall_fresh,
)
from services.api.app.recsys.rerank import ScoredItem, apply_explore_slot, mmr_rerank
from services.api.app.recsys.scoring import model_manager
from services.api.app.schemas import (
    DailyMetricOut,
    FeedItemOut,
    FeedResponse,
    ModelInfoOut,
    PaperOut,
    ProfileInfoOut,
    SavedItemOut,
    SavedResponse,
    StatsResponse,
)

COLD_START_INTERACTIONS = 10
CANDIDATE_POOL_HINT = 300  # recall routes are sized to land around here (spec §7)

router = APIRouter()


def _paper_out(paper: Paper) -> PaperOut:
    return PaperOut(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        abstract=paper.abstract,
        authors=paper.authors or [],
        categories=paper.categories or [],
        primary_category=paper.primary_category,
        published_at=paper.published_at,
        pdf_url=paper.pdf_url,
        citation_count=paper.citation_count,
    )


def _reason(cand: Candidate, octx: OnlineContext) -> str:
    if cand.source == "vector":
        best_title, best_sim = None, -2.0
        for sp in octx.saved_papers:
            sim = cosine(
                sp.embedding,
                None if cand.paper.embedding is None else cand.paper.embedding,
            )
            if sim is not None and sim > best_sim:
                best_title, best_sim = sp.title, sim
        return f"与你收藏的《{best_title}》相关" if best_title else "与你的兴趣画像相关"
    if cand.source == "graph":
        title = octx.positive_titles.get(cand.related_positive_id or "")
        return f"引用了你读过的《{title}》" if title else "与你读过的论文有引用关联"
    if cand.source == "fresh":
        return "今日新发布"
    return "探索推荐"


def _to_scored_item(cand: Candidate, score: float) -> ScoredItem:
    import numpy as np

    return ScoredItem(
        key=cand.paper.arxiv_id,
        score=score,
        embedding=(
            np.asarray(cand.paper.embedding, dtype=np.float32)
            if cand.paper.embedding is not None
            else None
        ),
        primary_category=cand.paper.primary_category,
        recall_source=cand.source,
        payload=cand,
    )


def _interleaving_enabled(profile_row: UserProfile) -> bool:
    return bool((profile_row.config or {}).get("interleaving_enabled", False))


@router.get("/feed", response_model=FeedResponse)
def get_feed(n: int = Query(default=20, ge=1, le=50), session: Session = DbSession):
    now = datetime.now(UTC)
    octx = load_online_context(session)
    interaction_count = octx.profile_row.interaction_count or 0

    cold_start = interaction_count < COLD_START_INTERACTIONS

    if cold_start:
        # Cold start: fresh route only, ranked by citation_velocity (spec §7).
        excluded = excluded_paper_ids(session, now)
        papers = recall_fresh(session, excluded, now)
        candidates = [Candidate(paper=p, source="fresh") for p in papers]
    else:
        candidates = recall_all(session, octx.ctx.profile_embedding, now)

    features_by_key = {
        c.paper.arxiv_id: compute_candidate_features(c.paper, octx.ctx, c.source, now)
        for c in candidates
    }
    cand_by_key = {c.paper.arxiv_id: c for c in candidates}

    prod = model_manager.production
    staging = model_manager.staging
    feats_list = [features_by_key[k] for k in cand_by_key]
    keys = list(cand_by_key)
    prod_scores = dict(zip(keys, prod.score(feats_list), strict=True)) if keys else {}

    arm_by_key: dict[str, str | None] = {}
    score_by_key: dict[str, float] = dict(prod_scores)
    version_by_key: dict[str, str] = {k: prod.version for k in keys}

    if cold_start:
        # Keep the recall ordering (citation_velocity desc); still snapshot
        # features + rule score for future training data.
        selected = [_to_scored_item(cand_by_key[k], prod_scores.get(k, 0.0)) for k in keys][:n]
    elif staging is not None and _interleaving_enabled(octx.profile_row):
        chal_scores = dict(zip(keys, staging.score(feats_list), strict=True))
        prod_items = [_to_scored_item(cand_by_key[k], prod_scores[k]) for k in keys]
        chal_items = [_to_scored_item(cand_by_key[k], chal_scores[k]) for k in keys]
        # MMR each arm's ranking first, then team-draft merge — keeps both the
        # diversity constraint and clean per-arm credit attribution.
        prod_rank = [it.key for it in mmr_rerank(prod_items, n)]
        chal_rank = [it.key for it in mmr_rerank(chal_items, n)]
        drafted = team_draft(prod_rank, chal_rank, n)
        for d in drafted:
            arm_by_key[d.key] = d.arm
            if d.arm == ARM_CHALLENGER:
                score_by_key[d.key] = chal_scores[d.key]
                version_by_key[d.key] = staging.version
        selected = [_to_scored_item(cand_by_key[d.key], score_by_key[d.key]) for d in drafted]
    else:
        items = [_to_scored_item(cand_by_key[k], prod_scores[k]) for k in keys]
        selected = mmr_rerank(items, n)

    if not cold_start:
        explore_pool = [
            _to_scored_item(c, prod_scores.get(c.paper.arxiv_id, 0.0))
            for c in candidates
            if c.source == "explore"
        ]
        selected = apply_explore_slot(selected, explore_pool)

    # Write impressions in the same transaction as the response (spec §7 step 5).
    request_id = uuid.uuid4()
    items_out: list[FeedItemOut] = []
    for pos, item in enumerate(selected, start=1):
        cand: Candidate = item.payload
        impression_id = uuid.uuid4()
        session.add(
            Impression(
                impression_id=impression_id,
                request_id=request_id,
                paper_id=cand.paper.arxiv_id,
                position=pos,
                recall_source=cand.source,
                model_version=version_by_key.get(cand.paper.arxiv_id, prod.version),
                score=float(score_by_key.get(cand.paper.arxiv_id, 0.0)),
                features=features_by_key[cand.paper.arxiv_id],
                interleave_arm=arm_by_key.get(cand.paper.arxiv_id),
            )
        )
        items_out.append(
            FeedItemOut(
                impression_id=impression_id,
                position=pos,
                recall_source=cand.source,
                reason=_reason(cand, octx),
                paper=_paper_out(cand.paper),
            )
        )
    return FeedResponse(request_id=request_id, items=items_out)


@router.get("/saved", response_model=SavedResponse)
def get_saved(session: Session = DbSession):
    rows = session.execute(
        select(Paper, func.max(Feedback.created_at).label("saved_at"))
        .join(Impression, Impression.paper_id == Paper.arxiv_id)
        .join(Feedback, Feedback.impression_id == Impression.impression_id)
        .where(Feedback.event_type == "save")
        .group_by(Paper.arxiv_id)
        .order_by(func.max(Feedback.created_at).desc())
    ).all()
    return SavedResponse(
        items=[SavedItemOut(saved_at=saved_at, paper=_paper_out(p)) for p, saved_at in rows]
    )


@router.get("/stats", response_model=StatsResponse)
def get_stats(session: Session = DbSession):
    since = datetime.now(UTC).date() - timedelta(days=90)
    daily = session.scalars(
        select(MetricsDaily).where(MetricsDaily.day >= since).order_by(MetricsDaily.day)
    ).all()

    def _model_info(status: str) -> ModelInfoOut | None:
        row = session.scalars(
            select(ModelRegistry)
            .where(ModelRegistry.status == status)
            .order_by(ModelRegistry.created_at.desc())
        ).first()
        if row is None:
            return None
        return ModelInfoOut(
            version=row.version,
            model_type=row.model_type,
            status=row.status,
            created_at=row.created_at,
            metrics=row.metrics,
        )

    profile_row = session.get(UserProfile, "default")
    return StatsResponse(
        daily=[DailyMetricOut.model_validate(d, from_attributes=True) for d in daily],
        models={"production": _model_info("production"), "staging": _model_info("staging")},
        profile=ProfileInfoOut(
            interaction_count=(profile_row.interaction_count or 0) if profile_row else 0,
            updated_at=profile_row.updated_at if profile_row else None,
        ),
    )
