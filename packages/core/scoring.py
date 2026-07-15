"""V0 rule score (spec §8.1) — pure function over a feature snapshot.

Lives in packages/core (not services/api) because evaluate.py must replay the
same formula over historical snapshots as the offline baseline (spec §9.3).
"""

import math

RULE_MODEL_VERSION = "rule-v0"

_CITATION_NORM = math.log1p(100.0)


def rule_score(features: dict[str, float]) -> float:
    """score = 0.60·cos_profile + 0.25·exp(−hours/72) + 0.15·min(log1p(c)/log1p(100), 1)

    cos_profile already carries the 0.5 cold-start constant (features.py).
    """
    cos_term = float(features.get("cos_profile", 0.5))
    freshness = math.exp(-float(features.get("hours_since_pub", 0.0)) / 72.0)
    citation = min(float(features.get("log_citations", 0.0)) / _CITATION_NORM, 1.0)
    return 0.60 * cos_term + 0.25 * freshness + 0.15 * citation
