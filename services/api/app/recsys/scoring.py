"""Model scoring + hot reload (spec §7 /admin/reload-model).

The service holds a production scorer (and optionally a staging challenger).
A background loop re-reads model_registry every 10 minutes and reloads on
version change. LightGBM artifacts are pulled from R2 into a local cache.
"""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.core.features import features_to_matrix
from packages.core.models import ModelRegistry
from packages.core.scoring import RULE_MODEL_VERSION, rule_score

logger = logging.getLogger("api.scoring")


@dataclass
class Scorer:
    version: str
    model_type: str  # 'rule'|'lightgbm'
    booster: object | None = None  # lightgbm.Booster for model_type='lightgbm'

    def score(self, feature_dicts: list[dict[str, float]]) -> list[float]:
        if self.model_type == "rule":
            return [rule_score(f) for f in feature_dicts]
        matrix = features_to_matrix(feature_dicts)
        return list(self.booster.predict(matrix))


def _download_artifact(artifact_uri: str, version: str) -> Path:
    """s3://bucket/key -> local cache file (R2 via S3-compatible API)."""
    import boto3

    settings = get_settings()
    cache_dir = Path(settings.model_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    local = cache_dir / f"{version}.txt"
    if local.exists():
        return local
    bucket_key = artifact_uri.removeprefix("s3://")
    bucket, _, key = bucket_key.partition("/")
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    s3.download_file(bucket, key, str(local))
    return local


def load_scorer(row: ModelRegistry) -> Scorer:
    if row.model_type == "rule":
        return Scorer(version=row.version, model_type="rule")
    import lightgbm as lgb

    path = _download_artifact(row.artifact_uri, row.version)
    booster = lgb.Booster(model_file=str(path))
    return Scorer(version=row.version, model_type="lightgbm", booster=booster)


class ModelManager:
    """Holds current production/staging scorers; thread-safe reload."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._production = Scorer(version=RULE_MODEL_VERSION, model_type="rule")
        self._staging: Scorer | None = None

    @property
    def production(self) -> Scorer:
        with self._lock:
            return self._production

    @property
    def staging(self) -> Scorer | None:
        with self._lock:
            return self._staging

    def reload(self, session: Session) -> dict[str, str | None]:
        rows = session.scalars(
            select(ModelRegistry).where(ModelRegistry.status.in_(("production", "staging")))
        ).all()
        prod_row = next((r for r in rows if r.status == "production"), None)
        # Newest staging wins if several exist.
        staging_rows = sorted(
            (r for r in rows if r.status == "staging"),
            key=lambda r: r.created_at or 0,
            reverse=True,
        )
        staging_row = staging_rows[0] if staging_rows else None

        with self._lock:
            current_prod, current_staging = self._production, self._staging
        try:
            if prod_row is not None and prod_row.version != current_prod.version:
                current_prod = load_scorer(prod_row)
                logger.info("loaded production model %s", current_prod.version)
            if staging_row is None:
                current_staging = None
            elif current_staging is None or staging_row.version != current_staging.version:
                current_staging = load_scorer(staging_row)
                logger.info("loaded staging model %s", current_staging.version)
        except Exception:
            # Keep serving with the previous model rather than dying mid-request.
            logger.exception("model reload failed; keeping current models")

        with self._lock:
            self._production, self._staging = current_prod, current_staging
        return {
            "production": current_prod.version,
            "staging": current_staging.version if current_staging else None,
        }


model_manager = ModelManager()
