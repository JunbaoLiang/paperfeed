"""M5 acceptance (spec §12): synthetic 3000-impression fixture through the full
offline chain — dataset → LightGBM training → MLflow run → evaluation →
staging decision — with a local file:// MLflow store and --dry-run (no DB/R2).
"""

import json
import sys
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from packages.core.features import FEATURE_ORDER
from pipelines.evaluate import baseline_scores, decide_staging, evaluate_scores
from pipelines.train import time_split, train_model

N_REQUESTS = 150
PER_REQUEST = 20  # 150 × 20 = 3000 impressions
START = datetime(2026, 5, 1, tzinfo=UTC)


def synthetic_dataset(seed: int = 0) -> pd.DataFrame:
    """Signal lives in author_seen_cnt / mean_sim_last5_clicked — features the
    rule score ignores, so a working LightGBM must beat the rule baseline."""
    rng = np.random.default_rng(seed)
    rows = []
    for r in range(N_REQUESTS):
        shown = START + timedelta(days=60 * r / N_REQUESTS)
        for pos in range(1, PER_REQUEST + 1):
            author_cnt = float(rng.integers(0, 5))
            sim5 = float(rng.uniform(0, 1))
            f = {
                "cos_profile": float(rng.uniform(0.3, 0.9)),
                "hours_since_pub": float(rng.uniform(1, 500)),
                "log_citations": float(rng.uniform(0, 5)),
                "citation_velocity": float(rng.uniform(0, 20)),
                "cat_match_cnt": float(rng.integers(0, 3)),
                "primary_cat_is_top1": float(rng.integers(0, 2)),
                "author_seen_cnt": author_cnt,
                "max_sim_saved": float(rng.uniform(0, 1)),
                "mean_sim_last5_clicked": sim5,
                "recall_vector": 1.0,
                "recall_graph": 0.0,
                "recall_fresh": 0.0,
                "recall_explore": 0.0,
                "hour_of_day": float(rng.integers(0, 24)),
                "is_weekend": float(rng.integers(0, 2)),
                "position": float(pos),
            }
            latent = author_cnt / 4.0 + sim5 + rng.normal(0, 0.15)
            label = 2 if latent > 1.5 else (1 if latent > 1.0 else 0)
            rows.append({**f, "label": label, "request_id": f"req-{r}", "shown_at": shown})
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def dataset() -> pd.DataFrame:
    df = synthetic_dataset()
    assert len(df) == 3000
    return df


def test_time_split_is_temporal(dataset):
    train_df, valid_df = time_split(dataset)
    assert not train_df.empty and not valid_df.empty
    assert pd.to_datetime(train_df["shown_at"]).max() <= pd.to_datetime(valid_df["shown_at"]).min()


def test_full_chain_train_evaluate_decide(dataset):
    df = dataset.sort_values(["request_id", "position"]).reset_index(drop=True)
    train_df, valid_df = time_split(df)
    booster, best_iter = train_model(train_df, valid_df)
    assert best_iter >= 1

    valid_df = valid_df.reset_index(drop=True)
    x_valid = valid_df[FEATURE_ORDER].to_numpy(dtype=np.float64)
    challenger = evaluate_scores(valid_df, booster.predict(x_valid))
    baseline = evaluate_scores(valid_df, baseline_scores(valid_df))

    assert challenger["ndcg@10"] is not None and baseline["ndcg@10"] is not None
    assert challenger["auc"] > 0.8  # the model must actually learn the signal
    # LightGBM sees the true signal features; rule-v0 cannot -> challenger wins
    assert decide_staging(challenger["ndcg@10"], baseline["ndcg@10"]) is True


def test_train_and_evaluate_entrypoints_with_mlflow(dataset, tmp_path, monkeypatch):
    """Run the real train.main() and evaluate.main() against a parquet fixture
    and a file:// MLflow store — verifies the MLflow run + meta handoff."""
    pytest.importorskip("mlflow")
    dataset_path = tmp_path / "dataset.parquet"
    meta_path = tmp_path / "meta.json"
    dataset.to_parquet(dataset_path, index=False)

    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.chdir(tmp_path)  # train writes model files under ./data
    from packages.core.config import get_settings

    get_settings.cache_clear()

    from pipelines import evaluate as evaluate_mod
    from pipelines import train as train_mod

    monkeypatch.setattr(
        sys,
        "argv",
        ["train", "--dataset", str(dataset_path), "--meta-out", str(meta_path)],
    )
    assert train_mod.main() == 0
    meta = json.loads(meta_path.read_text())
    assert meta["skipped"] is False
    assert meta["version"].startswith("lgbm-")

    import mlflow

    run = mlflow.get_run(meta["mlflow_run_id"])
    assert run.data.metrics  # params/metrics logged

    monkeypatch.setattr(
        sys,
        "argv",
        ["evaluate", "--dataset", str(dataset_path), "--meta", str(meta_path), "--dry-run"],
    )
    assert evaluate_mod.main() == 0
    run = mlflow.get_run(meta["mlflow_run_id"])
    assert "valid_ndcg_at_10" in run.data.metrics
    assert "baseline_ndcg_at_10" in run.data.metrics

    get_settings.cache_clear()
