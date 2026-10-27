from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forge_links",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("repository", sa.Text(), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id"),
    )
    op.create_table(
        "published_comments",
        sa.Column("comment_id", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("remote_id", sa.Text(), nullable=True),
        sa.Column("remote_url", sa.Text(), nullable=True),
        sa.Column("published_body_hash", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["comment_id"],
            ["comments.id"],
        ),
        sa.PrimaryKeyConstraint("comment_id"),
    )


def downgrade() -> None:
    op.drop_table("published_comments")
    op.drop_table("forge_links")
