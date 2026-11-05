from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reviewers", sa.Column("ai", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "ai_reviewed_units",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column("change_hash", sa.Text(), nullable=False),
        sa.Column("findings", sa.Integer(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id", "path", "kind", "qualified_name", "change_hash"),
    )
    with op.batch_alter_table("ai_reviewed_units", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ai_reviewed_units_review_id"), ["review_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("ai_reviewed_units", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ai_reviewed_units_review_id"))
    op.drop_table("ai_reviewed_units")
    op.execute("ALTER TABLE reviewers DROP COLUMN ai")
