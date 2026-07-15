"""Feature computation — THE single implementation shared by online serving and
offline training (spec §9.2). A second implementation anywhere is forbidden.

Online: /feed computes features here and snapshots them into impressions.features.
Offline: build_dataset.py reads the snapshots verbatim and never recomputes.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

# Column order for the LightGBM feature matrix. Training and inference must both
# build matrices in exactly this order.
FEATURE_ORDER: list[str] = [
    "cos_profile",
    "hours_since_pub",
    "log_citations",
    "citation_velocity",
    "cat_match_cnt",
    "primary_cat_is_top1",
    "author_seen_cnt",
    "max_sim_saved",
    "mean_sim_last5_clicked",
    "recall_vector",
    "recall_graph",
    "recall_fresh",
    "recall_explore",
    "hour_of_day",
    "is_weekend",
    "position",
]

# position is used as a training-only feature; at inference it is fixed to a
# constant to neutralize position bias (spec §9.2).
INFERENCE_POSITION = 5.0

# cos_profile fallback when the profile (or paper embedding) is missing —
# matches the cold-start constant in the rule score (spec §8.1).
COLD_START_COS = 0.5


@dataclass
class PaperFeatureInput:
    """The slice of a paper needed for feature computation."""

    embedding: np.ndarray | None
    published_at: datetime
    citation_count: int | None
    citation_velocity: float | None
    categories: list[str]
    primary_category: str
    author_names: list[str]


@dataclass
class UserContext:
    """User-side state, assembled once per /feed request (or per training row —
    but training rows use snapshots, so in practice online only)."""

    profile_embedding: np.ndarray | None = None
    top_categories: list[str] = field(default_factory=list)  # desc by interaction freq
    positive_author_counts: dict[str, int] = field(default_factory=dict)
    saved_embeddings: list[np.ndarray] = field(default_factory=list)
    last5_clicked_embeddings: list[np.ndarray] = field(default_factory=list)


def cosine(a: np.ndarray | None, b: np.ndarray | None) -> float | None:
    if a is None or b is None:
        return None
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return None
    return float(np.dot(a, b) / (na * nb))


def compute_features(
    paper: PaperFeatureInput,
    ctx: UserContext,
    recall_source: str,
    now: datetime,
    position: int | None = None,
) -> dict[str, float]:
    """Returns the full feature dict (keys == FEATURE_ORDER)."""
    cos_profile = cosine(ctx.profile_embedding, paper.embedding)
    if cos_profile is None:
        cos_profile = COLD_START_COS

    hours_since_pub = max((now - paper.published_at).total_seconds() / 3600.0, 0.0)
    log_citations = math.log1p(float(paper.citation_count or 0))

    cat_match_cnt = float(len(set(paper.categories) & set(ctx.top_categories)))
    primary_cat_is_top1 = float(
        bool(ctx.top_categories) and paper.primary_category == ctx.top_categories[0]
    )
    author_seen_cnt = float(
        sum(ctx.positive_author_counts.get(name, 0) for name in paper.author_names)
    )

    saved_sims = [s for e in ctx.saved_embeddings if (s := cosine(paper.embedding, e)) is not None]
    max_sim_saved = max(saved_sims) if saved_sims else 0.0
    clicked_sims = [
        s for e in ctx.last5_clicked_embeddings if (s := cosine(paper.embedding, e)) is not None
    ]
    mean_sim_last5_clicked = float(np.mean(clicked_sims)) if clicked_sims else 0.0

    return {
        "cos_profile": cos_profile,
        "hours_since_pub": hours_since_pub,
        "log_citations": log_citations,
        "citation_velocity": float(paper.citation_velocity or 0.0),
        "cat_match_cnt": cat_match_cnt,
        "primary_cat_is_top1": primary_cat_is_top1,
        "author_seen_cnt": author_seen_cnt,
        "max_sim_saved": max_sim_saved,
        "mean_sim_last5_clicked": mean_sim_last5_clicked,
        "recall_vector": float(recall_source == "vector"),
        "recall_graph": float(recall_source == "graph"),
        "recall_fresh": float(recall_source == "fresh"),
        "recall_explore": float(recall_source == "explore"),
        # SPEC-GAP: hour_of_day/is_weekend computed in UTC (single-user; spec
        # does not specify a timezone).
        "hour_of_day": float(now.hour),
        "is_weekend": float(now.weekday() >= 5),
        "position": float(position) if position is not None else INFERENCE_POSITION,
    }


def features_to_matrix(feature_dicts: list[dict[str, float]]) -> np.ndarray:
    """Feature dicts -> matrix in FEATURE_ORDER, for LightGBM train/predict."""
    return np.array(
        [[float(f.get(name, 0.0)) for name in FEATURE_ORDER] for f in feature_dicts],
        dtype=np.float64,
    )
