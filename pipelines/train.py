"""Weekly LightGBM training (spec §6.5/§9). lambdarank, label_gain=[0,1,3],
group = request_id, strong regularization for the small single-user sample.

Writes data/train_meta.json for evaluate.py and logs everything to MLflow.
"""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from packages.core.config import get_settings
from packages.core.features import FEATURE_ORDER
from packages.core.logging import get_logger, log_event

logger = get_logger("pipelines.train")

MIN_TRAIN_ROWS = 2000  # V2 entry condition (spec §9): don't train before this
VALIDATION_DAYS = 14  # time-based split (spec §9.3)
DEFAULT_META = "data/train_meta.json"

LGBM_PARAMS = {
    "objective": "lambdarank",
    "label_gain": [0, 1, 3],
    "metric": "ndcg",
    "ndcg_eval_at": [10],
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "verbosity": -1,
}
NUM_BOOST_ROUND = 300
EARLY_STOPPING = 30


def time_split(df, validation_days: int = VALIDATION_DAYS):
    """Last N days as validation (spec §9.3). Assumes a shown_at column."""
    import pandas as pd

    shown = pd.to_datetime(df["shown_at"], utc=True)
    cutoff = shown.max() - timedelta(days=validation_days)
    return df[shown <= cutoff].copy(), df[shown > cutoff].copy()


def _group_sizes(df) -> list[int]:
    # LightGBM groups must be contiguous: caller sorts by request_id first.
    return df.groupby("request_id", sort=False).size().tolist()


def train_model(train_df, valid_df, params: dict | None = None):
    """Returns (booster, best_iteration). Both frames must be request-sorted."""
    import lightgbm as lgb

    params = params or LGBM_PARAMS
    x_train = train_df[FEATURE_ORDER].to_numpy(dtype=np.float64)
    x_valid = valid_df[FEATURE_ORDER].to_numpy(dtype=np.float64)
    dtrain = lgb.Dataset(x_train, label=train_df["label"].to_numpy(), group=_group_sizes(train_df))
    dvalid = lgb.Dataset(
        x_valid,
        label=valid_df["label"].to_numpy(),
        group=_group_sizes(valid_df),
        reference=dtrain,
    )
    booster = lgb.train(
        params,
        dtrain,
        num_boost_round=NUM_BOOST_ROUND,
        valid_sets=[dvalid],
        valid_names=["valid"],
        callbacks=[lgb.early_stopping(EARLY_STOPPING, verbose=False)],
    )
    return booster, booster.best_iteration


def make_version(dataset_fingerprint: str, now: datetime) -> str:
    short = hashlib.sha1(dataset_fingerprint.encode()).hexdigest()[:6]
    return f"lgbm-{now:%Y%m%d}-{short}"


def setup_mlflow():
    import mlflow

    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri or settings.database_url)
    mlflow.set_experiment("paperfeed")
    return mlflow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/dataset.parquet")
    parser.add_argument("--meta-out", default=DEFAULT_META)
    parser.add_argument("--min-rows", type=int, default=MIN_TRAIN_ROWS)
    parser.add_argument("--force", action="store_true", help="train below --min-rows")
    args = parser.parse_args()

    import pandas as pd

    df = pd.read_parquet(args.dataset)
    if len(df) < args.min_rows and not args.force:
        log_event(logger, "train_skipped", rows=len(df), min_rows=args.min_rows)
        Path(args.meta_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.meta_out).write_text(json.dumps({"skipped": True, "rows": len(df)}))
        return 0

    df = df.sort_values(["request_id", "position"]).reset_index(drop=True)
    train_df, valid_df = time_split(df)
    if train_df.empty or valid_df.empty:
        log_event(logger, "train_skipped_empty_split", train=len(train_df), valid=len(valid_df))
        Path(args.meta_out).write_text(json.dumps({"skipped": True, "reason": "empty_split"}))
        return 0

    now = datetime.now(UTC)
    version = make_version(f"{len(df)}-{df['shown_at'].max()}", now)
    model_path = Path("data") / f"{version}.txt"
    model_path.parent.mkdir(parents=True, exist_ok=True)

    mlflow = setup_mlflow()
    with mlflow.start_run(run_name=version) as run:
        booster, best_iter = train_model(train_df, valid_df)
        booster.save_model(str(model_path), num_iteration=best_iter)

        mlflow.log_params({**LGBM_PARAMS, "label_gain": "0,1,3", "ndcg_eval_at": "10"})
        mlflow.log_params(
            {"rows": len(df), "train_rows": len(train_df), "valid_rows": len(valid_df)}
        )
        valid_ndcg = booster.best_score.get("valid", {}).get("ndcg@10")
        if valid_ndcg is not None:
            mlflow.log_metric("valid_ndcg10_lgb", valid_ndcg)

        try:
            import matplotlib

            matplotlib.use("Agg")
            import lightgbm as lgb
            import matplotlib.pyplot as plt

            ax = lgb.plot_importance(booster, max_num_features=len(FEATURE_ORDER))
            ax.figure.tight_layout()
            fig_path = Path("data") / f"{version}-importance.png"
            ax.figure.savefig(fig_path)
            plt.close(ax.figure)
            mlflow.log_artifact(str(fig_path))
        except Exception:
            logger.exception("importance_plot_failed")

        mlflow.log_artifact(str(model_path))
        run_id = run.info.run_id

    meta = {
        "skipped": False,
        "version": version,
        "model_path": str(model_path),
        "mlflow_run_id": run_id,
        "best_iteration": best_iter,
    }
    Path(args.meta_out).write_text(json.dumps(meta, indent=2))
    log_event(logger, "train_done", **meta)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("train_failed")
        sys.exit(1)
