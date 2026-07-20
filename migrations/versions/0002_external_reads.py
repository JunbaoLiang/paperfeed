"""external_reads queue: papers the user read outside the feed (spec v1.2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-17

"""

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_reads",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("arxiv_id", sa.Text(), sa.ForeignKey("papers.arxiv_id"), nullable=False),
        sa.Column("noted_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        # NULL = waiting for the paper's embedding; the nightly job materializes
        # the impression (with a real feature snapshot) and stamps this.
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_extread_pending", "external_reads", ["processed_at"])


def downgrade() -> None:
    op.drop_table("external_reads")
