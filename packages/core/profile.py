"""User profile vector math (spec §8.2) — pure functions, no DB access.

profile = normalize( Σ_i  w(type_i) · 0.5^(Δdays_i/30) · e_i )
w: save=+3.0, click_pdf=+2.0, click_abstract=+1.0, dwell>20s=+1.0 (max with
click, not additive), dismiss=−1.5. Only events from the last 180 days count.
"""

from dataclasses import dataclass
from datetime import datetime

import numpy as np

# external_read: user read the paper outside the feed and told us — as strong
# as a save (SPEC-GAP: weight not in spec §8.2, added in v1.2).
POSITIVE_WEIGHTS = {"save": 3.0, "external_read": 3.0, "click_pdf": 2.0, "click_abstract": 1.0}
DWELL_WEIGHT = 1.0
DWELL_MS_THRESHOLD = 20_000.0
DISMISS_WEIGHT = -1.5
HALF_LIFE_DAYS = 30.0
MAX_EVENT_AGE_DAYS = 180.0

# Events that count toward interaction_count (cold-start threshold). 'visible'
# is passive exposure, not an interaction. SPEC-GAP: spec doesn't enumerate.
INTERACTION_EVENT_TYPES = frozenset(
    {"click_abstract", "click_pdf", "save", "dismiss", "external_read"}
)


@dataclass
class ImpressionInteraction:
    """All feedback on one impression, collapsed for profile computation."""

    embedding: np.ndarray
    event_types: set[str]
    dwell_ms: float | None
    latest_event_at: datetime


def interaction_weight(event_types: set[str], dwell_ms: float | None) -> float:
    """Per-impression weight: max over positive signals (dwell doesn't stack
    with clicks), plus the dismiss penalty if present."""
    pos = max(
        [w for t, w in POSITIVE_WEIGHTS.items() if t in event_types]
        + ([DWELL_WEIGHT] if (dwell_ms or 0.0) > DWELL_MS_THRESHOLD else [])
        + [0.0]
    )
    neg = DISMISS_WEIGHT if "dismiss" in event_types else 0.0
    return pos + neg


def compute_profile_vector(
    interactions: list[ImpressionInteraction], now: datetime
) -> np.ndarray | None:
    """Full recompute (single user, small event volume — no incremental logic).

    Positive and negative contributions are accumulated separately, summed,
    then the result is normalized (spec §8.2). Returns None when there is no
    signal (empty input or zero vector).
    """
    pos_sum = np.zeros(0)
    neg_sum = np.zeros(0)
    for it in interactions:
        age_days = (now - it.latest_event_at).total_seconds() / 86400.0
        if age_days > MAX_EVENT_AGE_DAYS or age_days < 0:
            continue
        w = interaction_weight(it.event_types, it.dwell_ms)
        if w == 0.0:
            continue
        contrib = w * (0.5 ** (age_days / HALF_LIFE_DAYS)) * it.embedding
        if w > 0:
            pos_sum = contrib if pos_sum.size == 0 else pos_sum + contrib
        else:
            neg_sum = contrib if neg_sum.size == 0 else neg_sum + contrib

    if pos_sum.size == 0 and neg_sum.size == 0:
        return None
    total = (pos_sum if pos_sum.size else 0.0) + (neg_sum if neg_sum.size else 0.0)
    norm = float(np.linalg.norm(total))
    if norm == 0.0:
        return None
    return total / norm
