from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_review_runs",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_label", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("again", sa.Boolean(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reviewed", sa.Integer(), nullable=False),
        sa.Column("findings", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ai_review_runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ai_review_runs_review_id"), ["review_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("ai_review_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ai_review_runs_review_id"))
    op.drop_table("ai_review_runs")
