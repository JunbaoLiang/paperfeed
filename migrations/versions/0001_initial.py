"""initial schema (spec §5) + citations + profile_history + seeds

Revision ID: 0001
Revises:
Create Date: 2026-07-14

"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None

DIM = 768


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "papers",
        sa.Column("arxiv_id", sa.Text(), primary_key=True),
        sa.Column("latest_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("authors", JSONB(), nullable=False),
        sa.Column("categories", ARRAY(sa.Text()), nullable=False),
        sa.Column("primary_category", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arxiv_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pdf_url", sa.Text()),
        sa.Column("s2_paper_id", sa.Text()),
        sa.Column("citation_count", sa.Integer()),
        sa.Column("citation_velocity", sa.REAL()),
        sa.Column("embedding", Vector(DIM)),
        sa.Column("embedding_model", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE INDEX idx_papers_emb ON papers USING hnsw (embedding vector_cosine_ops)")
    op.create_index("idx_papers_pub", "papers", [sa.text("published_at DESC")])

    op.create_table(
        "citations",
        sa.Column("src_id", sa.Text(), sa.ForeignKey("papers.arxiv_id"), primary_key=True),
        sa.Column("dst_id", sa.Text(), sa.ForeignKey("papers.arxiv_id"), primary_key=True),
    )

    op.create_table(
        "user_profile",
        sa.Column("profile_id", sa.Text(), primary_key=True, server_default=sa.text("'default'")),
        sa.Column("embedding", Vector(DIM)),
        sa.Column("interaction_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("config", JSONB()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "impressions",
        sa.Column(
            "impression_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("paper_id", sa.Text(), sa.ForeignKey("papers.arxiv_id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("recall_source", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("score", sa.REAL(), nullable=False),
        sa.Column("features", JSONB(), nullable=False),
        sa.Column("interleave_arm", sa.Text()),
        sa.Column("shown_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_impr_time", "impressions", ["shown_at"])
    op.create_index("idx_impr_paper", "impressions", ["paper_id"])

    op.create_table(
        "feedback",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "impression_id",
            UUID(as_uuid=True),
            sa.ForeignKey("impressions.impression_id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("value", sa.REAL()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_fb_impr", "feedback", ["impression_id"])

    op.create_table(
        "model_registry",
        sa.Column("version", sa.Text(), primary_key=True),
        sa.Column("model_type", sa.Text(), nullable=False),
        sa.Column("artifact_uri", sa.Text()),
        sa.Column("metrics", JSONB()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'staging'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "metrics_daily",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("impressions", sa.Integer()),
        sa.Column("clicks", sa.Integer()),
        sa.Column("saves", sa.Integer()),
        sa.Column("dismisses", sa.Integer()),
        sa.Column("ctr", sa.REAL()),
        sa.Column("profile_drift", sa.REAL()),
        sa.Column("model_version", sa.Text()),
    )

    op.create_table(
        "profile_history",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("embedding", Vector(DIM)),
    )

    # Seeds: initial production model (spec §5) and the single-user profile row
    # (SPEC-GAP: seeding the 'default' row here so online code can assume it exists).
    op.execute(
        "INSERT INTO model_registry (version, model_type, artifact_uri, metrics, status) "
        "VALUES ('rule-v0', 'rule', NULL, NULL, 'production')"
    )
    op.execute("INSERT INTO user_profile (profile_id) VALUES ('default')")


def downgrade() -> None:
    op.drop_table("profile_history")
    op.drop_table("metrics_daily")
    op.drop_table("model_registry")
    op.drop_table("feedback")
    op.drop_table("impressions")
    op.drop_table("user_profile")
    op.drop_table("citations")
    op.drop_table("papers")
