"""MMR rerank + explore slot (spec §8.3, §7 step 4).

MMR(d) = λ·score(d) − (1−λ)·max_{s∈selected} cos(e_d, e_s), λ=0.7.
Skip a candidate that would make ≥3 consecutive items share a primary_category.
"""

from dataclasses import dataclass

import numpy as np

from packages.core.features import cosine

MMR_LAMBDA = 0.7
MAX_CATEGORY_RUN = 3
EXPLORE_SLOT = 15  # 1-based target position, ±2 tolerance (spec §7 step 4)
EXPLORE_SLOT_TOLERANCE = 2


@dataclass
class ScoredItem:
    """One candidate entering rerank. `key` identifies the paper; `payload` is
    opaque to this module (the router keeps the Candidate there)."""

    key: str
    score: float
    embedding: np.ndarray | None
    primary_category: str
    recall_source: str
    payload: object = None


def _minmax_normalize(items: list[ScoredItem]) -> dict[str, float]:
    # LightGBM scores are unbounded; normalize so λ keeps its meaning across models.
    scores = [it.score for it in items]
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-12:
        return {it.key: 1.0 for it in items}
    return {it.key: (it.score - lo) / (hi - lo) for it in items}


def _violates_category_run(selected: list[ScoredItem], candidate: ScoredItem) -> bool:
    if len(selected) < MAX_CATEGORY_RUN - 1:
        return False
    tail = selected[-(MAX_CATEGORY_RUN - 1) :]
    return all(it.primary_category == candidate.primary_category for it in tail)


def mmr_rerank(items: list[ScoredItem], k: int, lam: float = MMR_LAMBDA) -> list[ScoredItem]:
    if not items:
        return []
    norm = _minmax_normalize(items)
    remaining = sorted(items, key=lambda it: norm[it.key], reverse=True)
    selected: list[ScoredItem] = []

    while remaining and len(selected) < k:
        best, best_val, best_is_fallback = None, -np.inf, True
        for it in remaining:
            max_sim = max(
                (
                    s
                    for s in (cosine(it.embedding, s_it.embedding) for s_it in selected)
                    if s is not None
                ),
                default=0.0,
            )
            val = lam * norm[it.key] - (1 - lam) * max_sim
            violates = _violates_category_run(selected, it)
            # Prefer non-violating candidates; fall back if every one violates.
            if (not violates, val) > (not best_is_fallback, best_val):
                best, best_val, best_is_fallback = it, val, violates
        selected.append(best)
        remaining.remove(best)
    return selected


def apply_explore_slot(
    selected: list[ScoredItem], explore_pool: list[ScoredItem]
) -> list[ScoredItem]:
    """Force one explore-route item at position 15±2 when the feed is long
    enough. SPEC-GAP: implemented as replace-in-place (keeps feed length n);
    skipped when len(selected) < 13 or no explore candidate is available."""
    lo = EXPLORE_SLOT - EXPLORE_SLOT_TOLERANCE  # 13
    hi = EXPLORE_SLOT + EXPLORE_SLOT_TOLERANCE  # 17
    if len(selected) < lo:
        return selected
    window = selected[lo - 1 : min(hi, len(selected))]
    if any(it.recall_source == "explore" for it in window):
        return selected
    chosen_keys = {it.key for it in selected}
    replacement = next((it for it in explore_pool if it.key not in chosen_keys), None)
    if replacement is None:
        return selected
    slot_idx = min(EXPLORE_SLOT, len(selected)) - 1
    out = list(selected)
    out[slot_idx] = replacement
    return out
