"""Daily profile recompute (spec §6.4, formula §8.2). Full recompute — the
single-user event volume is tiny, incremental logic isn't worth it.

Also: encodes onboarding seed keywords with SPECTER2 when there is no
behavioral signal yet (spec §7 冷启动), refreshes interaction_count, and
snapshots the profile into profile_history for the drift metric.
"""

import sys
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import func, select

from packages.core.db import session_scope
from packages.core.logging import get_logger, log_event
from packages.core.models import Feedback, Impression, Paper, ProfileHistory, UserProfile
from packages.core.profile import (
    INTERACTION_EVENT_TYPES,
    ImpressionInteraction,
    compute_profile_vector,
)

logger = get_logger("pipelines.profile_update")


def collect_interactions(session) -> list[ImpressionInteraction]:
    rows = session.execute(
        select(
            Feedback.impression_id,
            Feedback.event_type,
            Feedback.value,
            Feedback.created_at,
            Paper.embedding,
        )
        .join(Impression, Impression.impression_id == Feedback.impression_id)
        .join(Paper, Paper.arxiv_id == Impression.paper_id)
        .where(Paper.embedding.is_not(None))
    ).all()

    by_impression: dict = {}
    for impression_id, event_type, value, created_at, embedding in rows:
        agg = by_impression.setdefault(
            impression_id,
            {
                "embedding": np.asarray(embedding, dtype=np.float32),
                "event_types": set(),
                "dwell_ms": None,
                "latest": created_at,
            },
        )
        agg["event_types"].add(event_type)
        if event_type == "dwell" and value is not None:
            agg["dwell_ms"] = max(agg["dwell_ms"] or 0.0, float(value))
        if created_at and created_at > agg["latest"]:
            agg["latest"] = created_at

    return [
        ImpressionInteraction(
            embedding=a["embedding"],
            event_types=a["event_types"],
            dwell_ms=a["dwell_ms"],
            latest_event_at=a["latest"],
        )
        for a in by_impression.values()
    ]


def encode_seed_keywords(keywords: list[str]) -> np.ndarray | None:
    """Mean of SPECTER2 keyword embeddings (offline job — torch is available here)."""
    from pipelines.embed import embed_texts, load_model

    if not keywords:
        return None
    tokenizer, model = load_model()
    vectors = embed_texts(tokenizer, model, keywords)
    mean = np.asarray(vectors).mean(axis=0)
    norm = float(np.linalg.norm(mean))
    return mean / norm if norm > 0 else None


def main() -> int:
    now = datetime.now(UTC)
    with session_scope() as session:
        interactions = collect_interactions(session)
        profile_vec = compute_profile_vector(interactions, now)

        profile = session.get(UserProfile, "default")
        if profile is None:
            profile = UserProfile(profile_id="default")
            session.add(profile)

        source = "behavior"
        if profile_vec is None:
            seeds = (profile.config or {}).get("seed_keywords") or []
            if seeds:
                profile_vec = encode_seed_keywords(seeds)
                source = "seed_keywords"

        interaction_count = session.scalar(
            select(func.count())
            .select_from(Feedback)
            .where(Feedback.event_type.in_(INTERACTION_EVENT_TYPES))
        )

        if profile_vec is not None:
            profile.embedding = profile_vec.tolist()
        profile.interaction_count = int(interaction_count or 0)
        profile.updated_at = now

        # Daily snapshot for the 30-day drift metric (spec §6.6). Idempotent per day.
        snapshot = session.get(ProfileHistory, now.date())
        if snapshot is None:
            session.add(
                ProfileHistory(
                    day=now.date(),
                    embedding=profile_vec.tolist() if profile_vec is not None else None,
                )
            )
        elif profile_vec is not None:
            snapshot.embedding = profile_vec.tolist()

        log_event(
            logger,
            "profile_updated",
            source=source,
            has_vector=profile_vec is not None,
            interactions=len(interactions),
            interaction_count=int(interaction_count or 0),
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("profile_update_failed")
        sys.exit(1)
