"""Offline evaluation (spec §9.3): time split, NDCG@10 / AUC / Recall@20,
rule-v0 baseline replay on the same validation set. Challenger wins with
NDCG@10 ≥ baseline +5% → upload to R2, register as staging, enable interleaving.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from packages.core.config import get_settings
from packages.core.features import FEATURE_ORDER
from packages.core.logging import get_logger, log_event
from packages.core.scoring import rule_score

logger = get_logger("pipelines.evaluate")

LABEL_GAIN = {0: 0.0, 1: 1.0, 2: 3.0}  # consistent with lambdarank label_gain
WIN_THRESHOLD = 1.05  # challenger needs +5% NDCG@10 over baseline


def _dcg(labels: list[int], k: int) -> float:
    return sum(
        LABEL_GAIN.get(int(label), 0.0) / math.log2(i + 2) for i, label in enumerate(labels[:k])
    )


def ndcg_at_k(
    labels_by_group: list[list[int]], scores_by_group: list[list[float]], k: int
) -> float | None:
    """Mean NDCG@k over groups that have at least one positive label."""
    vals = []
    for labels, scores in zip(labels_by_group, scores_by_group, strict=True):
        if not any(label > 0 for label in labels):
            continue
        order = np.argsort(scores)[::-1]
        ranked = [labels[i] for i in order]
        ideal = sorted(labels, reverse=True)
        idcg = _dcg(ideal, k)
        if idcg > 0:
            vals.append(_dcg(ranked, k) / idcg)
    return float(np.mean(vals)) if vals else None


def recall_at_k(
    labels_by_group: list[list[int]], scores_by_group: list[list[float]], k: int
) -> float | None:
    vals = []
    for labels, scores in zip(labels_by_group, scores_by_group, strict=True):
        n_pos = sum(1 for label in labels if label > 0)
        if n_pos == 0:
            continue
        order = np.argsort(scores)[::-1]
        hit = sum(1 for i in order[:k] if labels[i] > 0)
        vals.append(hit / n_pos)
    return float(np.mean(vals)) if vals else None


def auc_score(labels: list[int], scores: list[float]) -> float | None:
    binary = [1 if label > 0 else 0 for label in labels]
    if len(set(binary)) < 2:
        return None
    from sklearn.metrics import roc_auc_score

    return float(roc_auc_score(binary, scores))


def group_arrays(df, scores: np.ndarray) -> tuple[list[list[int]], list[list[float]]]:
    labels_by_group, scores_by_group = [], []
    df = df.reset_index(drop=True)
    for _, idx in df.groupby("request_id", sort=False).groups.items():
        labels_by_group.append(df.loc[idx, "label"].astype(int).tolist())
        scores_by_group.append([float(scores[i]) for i in idx])
    return labels_by_group, scores_by_group


def evaluate_scores(df, scores: np.ndarray) -> dict[str, float | None]:
    labels_g, scores_g = group_arrays(df, scores)
    return {
        "ndcg@10": ndcg_at_k(labels_g, scores_g, 10),
        "auc": auc_score(df["label"].astype(int).tolist(), scores.tolist()),
        "recall@20": recall_at_k(labels_g, scores_g, 20),
    }


def baseline_scores(df) -> np.ndarray:
    """Replay rule-v0 over the stored feature snapshots — never recomputed."""
    return np.array(
        [rule_score({name: row[name] for name in FEATURE_ORDER}) for _, row in df.iterrows()]
    )


def decide_staging(challenger_ndcg: float | None, baseline_ndcg: float | None) -> bool:
    if challenger_ndcg is None:
        return False
    if baseline_ndcg is None or baseline_ndcg <= 0:
        return challenger_ndcg > 0
    return challenger_ndcg >= baseline_ndcg * WIN_THRESHOLD


def upload_model_to_r2(model_path: Path, version: str) -> str:
    import boto3

    settings = get_settings()
    key = f"models/{version}.txt"
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    s3.upload_file(str(model_path), settings.r2_bucket, key)
    return f"s3://{settings.r2_bucket}/{key}"


def register_staging(version: str, artifact_uri: str, metrics: dict) -> None:
    from sqlalchemy import select

    from packages.core.db import session_scope
    from packages.core.models import ModelRegistry, UserProfile

    with session_scope() as session:
        # Archive any previous staging model first — one challenger at a time.
        for row in session.scalars(select(ModelRegistry).where(ModelRegistry.status == "staging")):
            row.status = "archived"
        session.add(
            ModelRegistry(
                version=version,
                model_type="lightgbm",
                artifact_uri=artifact_uri,
                metrics=metrics,
                status="staging",
            )
        )
        profile = session.get(UserProfile, "default")
        if profile is not None:
            profile.config = {**(profile.config or {}), "interleaving_enabled": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/dataset.parquet")
    parser.add_argument("--meta", default="data/train_meta.json")
    parser.add_argument("--dry-run", action="store_true", help="skip R2 upload + registration")
    args = parser.parse_args()

    meta_path = Path(args.meta)
    if not meta_path.exists():
        log_event(logger, "evaluate_skipped", reason="no_meta")
        return 0
    meta = json.loads(meta_path.read_text())
    if meta.get("skipped"):
        log_event(logger, "evaluate_skipped", reason="train_skipped")
        return 0

    import lightgbm as lgb
    import pandas as pd

    from pipelines.train import setup_mlflow, time_split

    df = pd.read_parquet(args.dataset).sort_values(["request_id", "position"])
    _, valid_df = time_split(df)
    valid_df = valid_df.reset_index(drop=True)

    booster = lgb.Booster(model_file=meta["model_path"])
    x_valid = valid_df[FEATURE_ORDER].to_numpy(dtype=np.float64)
    challenger_metrics = evaluate_scores(valid_df, booster.predict(x_valid))
    baseline_metrics = evaluate_scores(valid_df, baseline_scores(valid_df))

    win = decide_staging(challenger_metrics["ndcg@10"], baseline_metrics["ndcg@10"])
    log_event(
        logger,
        "evaluate_done",
        challenger=challenger_metrics,
        baseline=baseline_metrics,
        challenger_wins=win,
    )

    mlflow = setup_mlflow()
    with mlflow.start_run(run_id=meta["mlflow_run_id"]):
        for name, value in challenger_metrics.items():
            if value is not None:
                mlflow.log_metric(f"valid_{name.replace('@', '_at_')}", value)
        for name, value in baseline_metrics.items():
            if value is not None:
                mlflow.log_metric(f"baseline_{name.replace('@', '_at_')}", value)
        mlflow.log_metric("challenger_wins", int(win))

    if win and not args.dry_run:
        artifact_uri = upload_model_to_r2(Path(meta["model_path"]), meta["version"])
        register_staging(
            meta["version"],
            artifact_uri,
            {"challenger": challenger_metrics, "baseline": baseline_metrics},
        )
        log_event(logger, "staging_registered", version=meta["version"], uri=artifact_uri)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("evaluate_failed")
        sys.exit(1)
