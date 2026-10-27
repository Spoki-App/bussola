from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "threads",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_revision_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=True),
        sa.Column("qualified_name", sa.Text(), nullable=True),
        sa.Column("side", sa.Text(), nullable=True),
        sa.Column("unit_hash", sa.Text(), nullable=True),
        sa.Column("line_offset", sa.Integer(), nullable=True),
        sa.Column("line_text", sa.Text(), nullable=True),
        sa.Column("context_before", sa.JSON(), nullable=False),
        sa.Column("context_after", sa.JSON(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["reviewers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_revision_id"],
            ["revisions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("threads", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_threads_review_id"), ["review_id"], unique=False)

    op.create_table(
        "comments",
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["reviewers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["threads.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("comments", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_comments_thread_id"), ["thread_id"], unique=False)

    op.create_table(
        "thread_anchors",
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=True),
        sa.Column("qualified_name", sa.Text(), nullable=True),
        sa.Column("unit_hash", sa.Text(), nullable=True),
        sa.Column("line_offset", sa.Integer(), nullable=True),
        sa.Column("outdated", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["revisions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["threads.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id", "revision_id"),
    )
    with op.batch_alter_table("thread_anchors", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_thread_anchors_thread_id"), ["thread_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("thread_anchors", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_thread_anchors_thread_id"))

    op.drop_table("thread_anchors")
    with op.batch_alter_table("comments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_comments_thread_id"))

    op.drop_table("comments")
    with op.batch_alter_table("threads", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_threads_review_id"))

    op.drop_table("threads")
