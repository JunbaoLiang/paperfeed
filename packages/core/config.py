"""Central configuration. All external input comes through here (pydantic-settings).

Secrets are provided via environment variables (GitHub Secrets / HF Spaces
Secrets / Vercel env) — zero hardcoding, see spec §11/§13.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core ---
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/paperfeed"
    api_token: str = "dev-token"

    # --- Ingestion ---
    arxiv_categories: str = "cs.LG,cs.AI,cs.CL,stat.ML"
    s2_api_key: str | None = None

    # --- Artifact store (Cloudflare R2, S3-compatible) ---
    r2_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    r2_bucket: str = "paperfeed-mlflow"

    # --- MLflow ---
    mlflow_tracking_uri: str | None = None  # defaults to database_url when unset

    # --- Online service ---
    model_cache_dir: str = "/tmp/paperfeed_models"
    registry_poll_seconds: int = 600

    @field_validator("database_url")
    @classmethod
    def _normalize_scheme(cls, v: str) -> str:
        # Neon hands out postgres:// or postgresql:// URLs; SQLAlchemy needs the
        # psycopg3 driver spelled out.
        if v.startswith("postgres://"):
            v = "postgresql://" + v.removeprefix("postgres://")
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v.removeprefix("postgresql://")
        return v

    @property
    def arxiv_category_list(self) -> list[str]:
        return [c.strip() for c in self.arxiv_categories.split(",") if c.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
