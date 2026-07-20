from datetime import UTC, datetime, timedelta

import numpy as np

from packages.core.profile import (
    ImpressionInteraction,
    compute_profile_vector,
    interaction_weight,
)

NOW = datetime(2026, 7, 14, tzinfo=UTC)


def make_interaction(embedding, event_types, days_ago=0.0, dwell_ms=None):
    return ImpressionInteraction(
        embedding=np.asarray(embedding, dtype=np.float64),
        event_types=set(event_types),
        dwell_ms=dwell_ms,
        latest_event_at=NOW - timedelta(days=days_ago),
    )


def test_weights():
    assert interaction_weight({"save"}, None) == 3.0
    assert interaction_weight({"external_read"}, None) == 3.0
    assert interaction_weight({"click_pdf"}, None) == 2.0
    assert interaction_weight({"click_abstract"}, None) == 1.0
    assert interaction_weight({"dismiss"}, None) == -1.5
    assert interaction_weight({"visible"}, None) == 0.0


def test_dwell_does_not_stack_with_click():
    # dwell>20s alongside click_abstract: max(1,1)=1, not 2
    assert interaction_weight({"click_abstract", "dwell"}, 25_000) == 1.0
    # dwell alone above/below threshold
    assert interaction_weight({"dwell"}, 25_000) == 1.0
    assert interaction_weight({"dwell"}, 10_000) == 0.0
    # save dominates
    assert interaction_weight({"save", "dwell", "click_abstract"}, 30_000) == 3.0


def test_dismiss_combined_with_positive():
    assert interaction_weight({"click_abstract", "dismiss"}, None) == -0.5


def test_profile_normalized_and_decayed():
    e1, e2 = [1.0, 0.0], [0.0, 1.0]
    # same weight, but e2 is 30 days old -> decayed to half strength
    vec = compute_profile_vector(
        [make_interaction(e1, {"save"}), make_interaction(e2, {"save"}, days_ago=30)],
        NOW,
    )
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-9
    assert vec[0] / vec[1] == np.float64(2.0).item() or abs(vec[0] / vec[1] - 2.0) < 1e-9


def test_events_older_than_180d_ignored():
    vec = compute_profile_vector([make_interaction([1.0, 0.0], {"save"}, days_ago=181)], NOW)
    assert vec is None


def test_negative_pulls_away():
    vec = compute_profile_vector(
        [
            make_interaction([1.0, 0.0], {"save"}),
            make_interaction([0.0, 1.0], {"dismiss"}),
        ],
        NOW,
    )
    assert vec[0] > 0
    assert vec[1] < 0  # dismissed direction is negative


def test_empty_returns_none():
    assert compute_profile_vector([], NOW) is None
    assert compute_profile_vector([make_interaction([1, 0], {"visible"})], NOW) is None
