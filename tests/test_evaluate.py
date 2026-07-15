import numpy as np

from pipelines.evaluate import (
    auc_score,
    decide_staging,
    ndcg_at_k,
    recall_at_k,
)
from pipelines.promote import judge


def test_ndcg_perfect_ranking():
    labels = [[2, 1, 0, 0]]
    scores = [[4.0, 3.0, 2.0, 1.0]]
    assert abs(ndcg_at_k(labels, scores, 10) - 1.0) < 1e-9


def test_ndcg_worst_ranking_less_than_one():
    labels = [[2, 1, 0, 0]]
    scores = [[1.0, 2.0, 3.0, 4.0]]  # reversed
    val = ndcg_at_k(labels, scores, 10)
    assert val is not None and val < 1.0


def test_ndcg_skips_groups_without_positives():
    assert ndcg_at_k([[0, 0]], [[1.0, 2.0]], 10) is None


def test_recall_at_k():
    labels = [[1, 0, 2, 0]]
    scores = [[4.0, 3.0, 2.0, 1.0]]  # positives at ranks 1 and 3
    assert abs(recall_at_k(labels, scores, 2) - 0.5) < 1e-9
    assert abs(recall_at_k(labels, scores, 3) - 1.0) < 1e-9


def test_auc():
    assert auc_score([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auc_score([0, 0, 0], [0.1, 0.2, 0.3]) is None  # single class


def test_decide_staging_threshold():
    assert decide_staging(0.63, 0.60) is True  # exactly +5%
    assert decide_staging(0.629, 0.60) is False
    assert decide_staging(None, 0.60) is False
    assert decide_staging(0.5, None) is True


def test_interleave_judge():
    # not enough data yet
    assert judge(total_clicks=100, challenger_clicks=60, staging_age_days=3) == "wait"
    # enough clicks, challenger wins
    assert judge(200, 110, 3) == "promote"  # 55% > 52%
    # enough clicks, challenger loses
    assert judge(200, 100, 3) == "archive"  # 50%
    # time-based judgment with few clicks
    assert judge(50, 30, 15) == "promote"  # 60%
    assert judge(0, 0, 15) == "archive"


def test_group_arrays_alignment():
    import pandas as pd

    from pipelines.evaluate import group_arrays

    df = pd.DataFrame(
        {
            "request_id": ["r1", "r1", "r2", "r2"],
            "label": [2, 0, 1, 0],
        }
    )
    scores = np.array([0.9, 0.1, 0.8, 0.2])
    labels_g, scores_g = group_arrays(df, scores)
    assert labels_g == [[2, 0], [1, 0]]
    assert scores_g == [[0.9, 0.1], [0.8, 0.2]]
