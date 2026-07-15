from datetime import UTC, datetime, timedelta

import numpy as np

from packages.core.features import (
    FEATURE_ORDER,
    INFERENCE_POSITION,
    PaperFeatureInput,
    UserContext,
    compute_features,
    cosine,
    features_to_matrix,
)

NOW = datetime(2026, 7, 14, 15, 0, tzinfo=UTC)  # Tuesday


def make_paper(**overrides) -> PaperFeatureInput:
    defaults = dict(
        embedding=np.array([1.0, 0.0, 0.0]),
        published_at=NOW - timedelta(hours=24),
        citation_count=10,
        citation_velocity=2.5,
        categories=["cs.LG", "cs.AI"],
        primary_category="cs.LG",
        author_names=["Alice", "Bob"],
    )
    defaults.update(overrides)
    return PaperFeatureInput(**defaults)


def test_all_features_present_and_ordered():
    f = compute_features(make_paper(), UserContext(), "vector", NOW)
    assert set(f) == set(FEATURE_ORDER)
    matrix = features_to_matrix([f])
    assert matrix.shape == (1, len(FEATURE_ORDER))


def test_cos_profile_cold_start_constant():
    f = compute_features(make_paper(), UserContext(profile_embedding=None), "fresh", NOW)
    assert f["cos_profile"] == 0.5
    # missing paper embedding also falls back
    f2 = compute_features(
        make_paper(embedding=None),
        UserContext(profile_embedding=np.array([1.0, 0.0, 0.0])),
        "fresh",
        NOW,
    )
    assert f2["cos_profile"] == 0.5


def test_cos_profile_actual():
    ctx = UserContext(profile_embedding=np.array([1.0, 0.0, 0.0]))
    f = compute_features(make_paper(), ctx, "vector", NOW)
    assert abs(f["cos_profile"] - 1.0) < 1e-6


def test_recall_one_hot():
    f = compute_features(make_paper(), UserContext(), "graph", NOW)
    assert f["recall_graph"] == 1.0
    assert f["recall_vector"] == f["recall_fresh"] == f["recall_explore"] == 0.0


def test_category_and_author_features():
    ctx = UserContext(
        top_categories=["cs.LG", "stat.ML"],
        positive_author_counts={"Alice": 3, "Carol": 7},
    )
    f = compute_features(make_paper(), ctx, "vector", NOW)
    assert f["cat_match_cnt"] == 1.0  # cs.LG only
    assert f["primary_cat_is_top1"] == 1.0
    assert f["author_seen_cnt"] == 3.0  # Alice


def test_similarity_features():
    ctx = UserContext(
        saved_embeddings=[np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])],
        last5_clicked_embeddings=[np.array([1.0, 0.0, 0.0]), np.array([-1.0, 0.0, 0.0])],
    )
    f = compute_features(make_paper(), ctx, "vector", NOW)
    assert abs(f["max_sim_saved"] - 1.0) < 1e-6
    assert abs(f["mean_sim_last5_clicked"] - 0.0) < 1e-6


def test_position_defaults_to_inference_constant():
    f = compute_features(make_paper(), UserContext(), "vector", NOW)
    assert f["position"] == INFERENCE_POSITION
    f2 = compute_features(make_paper(), UserContext(), "vector", NOW, position=12)
    assert f2["position"] == 12.0


def test_time_features():
    f = compute_features(make_paper(), UserContext(), "vector", NOW)
    assert f["hours_since_pub"] == 24.0
    assert f["hour_of_day"] == 15.0
    assert f["is_weekend"] == 0.0


def test_cosine_handles_zero_and_none():
    assert cosine(None, np.array([1.0])) is None
    assert cosine(np.zeros(3), np.array([1.0, 0.0, 0.0])) is None
