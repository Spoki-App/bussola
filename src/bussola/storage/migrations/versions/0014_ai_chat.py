from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_chat_messages",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("snippets", sa.JSON(), nullable=False),
        sa.Column("lookups", sa.JSON(), nullable=False),
        sa.Column("provider_label", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ai_chat_messages", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ai_chat_messages_review_id"), ["review_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("ai_chat_messages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ai_chat_messages_review_id"))
    op.drop_table("ai_chat_messages")
