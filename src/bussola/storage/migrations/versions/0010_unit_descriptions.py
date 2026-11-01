from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "unit_descriptions",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column("change_hash", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False),
        sa.Column("impact_reason", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_label", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id", "path", "kind", "qualified_name", "change_hash"),
    )
    with op.batch_alter_table("unit_descriptions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_unit_descriptions_review_id"), ["review_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("unit_descriptions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_unit_descriptions_review_id"))
    op.drop_table("unit_descriptions")
