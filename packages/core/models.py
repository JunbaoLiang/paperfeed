"""SQLAlchemy ORM models — the single schema definition for the whole project.

The Alembic initial migration mirrors spec §5 exactly; keep the two in sync.
"""

import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    REAL,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 768

# feedback.event_type enum (spec §5)
EVENT_TYPES = frozenset({"visible", "click_abstract", "click_pdf", "save", "dismiss", "dwell"})

RECALL_SOURCES = ("vector", "graph", "fresh", "explore")


class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    arxiv_id: Mapped[str] = mapped_column(Text, primary_key=True)  # '2501.12345', no version
    latest_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    primary_category: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arxiv_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(Text)
    s2_paper_id: Mapped[str | None] = mapped_column(Text)
    citation_count: Mapped[int | None] = mapped_column(Integer)
    citation_velocity: Mapped[float | None] = mapped_column(REAL)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(Text)  # 'specter2@<adapter_rev>'
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Citation(Base):
    """src cites dst; only edges where both ends exist in papers (spec §6.2)."""

    __tablename__ = "citations"

    src_id: Mapped[str] = mapped_column(Text, ForeignKey("papers.arxiv_id"), primary_key=True)
    dst_id: Mapped[str] = mapped_column(Text, ForeignKey("papers.arxiv_id"), primary_key=True)


class UserProfile(Base):
    __tablename__ = "user_profile"

    profile_id: Mapped[str] = mapped_column(Text, primary_key=True, default="default")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    interaction_count: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Impression(Base):
    __tablename__ = "impressions"

    impression_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    paper_id: Mapped[str] = mapped_column(Text, ForeignKey("papers.arxiv_id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based
    recall_source: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(REAL, nullable=False)
    # Feature snapshot at scoring time. Training reads this verbatim — never recompute.
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    interleave_arm: Mapped[str | None] = mapped_column(Text)  # 'prod'|'challenger'|NULL
    shown_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    impression_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("impressions.impression_id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float | None] = mapped_column(REAL)  # dwell: milliseconds; else NULL
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    version: Mapped[str] = mapped_column(Text, primary_key=True)  # 'rule-v0'|'lgbm-...'
    model_type: Mapped[str] = mapped_column(Text, nullable=False)  # 'rule'|'lightgbm'
    artifact_uri: Mapped[str | None] = mapped_column(Text)  # R2 s3:// path; NULL for rule
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'staging'")
    )  # staging|production|archived
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class MetricsDaily(Base):
    __tablename__ = "metrics_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    impressions: Mapped[int | None] = mapped_column(Integer)
    clicks: Mapped[int | None] = mapped_column(Integer)
    saves: Mapped[int | None] = mapped_column(Integer)
    dismisses: Mapped[int | None] = mapped_column(Integer)
    ctr: Mapped[float | None] = mapped_column(REAL)
    profile_drift: Mapped[float | None] = mapped_column(REAL)
    model_version: Mapped[str | None] = mapped_column(Text)


class ProfileHistory(Base):
    """Daily profile snapshots, used for the 30-day drift metric (spec §6.6)."""

    __tablename__ = "profile_history"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
