from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parsed_blobs",
        sa.Column("object_id", sa.Text(), nullable=False),
        sa.Column("extractor", sa.Text(), nullable=False),
        sa.Column("extractor_version", sa.Integer(), nullable=False),
        sa.Column("units", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("object_id", "extractor", "extractor_version"),
    )
    op.create_table(
        "repos",
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("root_commit", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path"),
    )
    with op.batch_alter_table("repos", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_repos_root_commit"), ["root_commit"], unique=False)

    op.create_table(
        "reviewers",
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "reviews",
        sa.Column("repo_id", sa.Integer(), nullable=False),
        sa.Column("head_ref", sa.Text(), nullable=False),
        sa.Column("base_ref", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["repo_id"],
            ["repos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repo_id", "head_ref", "base_ref"),
    )
    with op.batch_alter_table("reviews", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_reviews_repo_id"), ["repo_id"], unique=False)

    op.create_table(
        "revisions",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("head_sha", sa.Text(), nullable=False),
        sa.Column("base_sha", sa.Text(), nullable=False),
        sa.Column("merge_base_sha", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id", "number"),
    )
    with op.batch_alter_table("revisions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_revisions_review_id"), ["review_id"], unique=False)

    op.create_table(
        "approvals",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column("head_hash", sa.Text(), nullable=True),
        sa.Column("base_hash", sa.Text(), nullable=True),
        sa.Column("approved_text", sa.Text(), nullable=True),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["reviewers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["revisions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("approvals", schema=None) as batch_op:
        batch_op.create_index("ix_approvals_review_reviewer", ["review_id", "reviewer_id"], unique=False)

    op.create_table(
        "review_sessions",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["reviewers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["revisions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("review_sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_review_sessions_review_id"), ["review_id"], unique=False)

    op.create_table(
        "row_approvals",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("row_hash", sa.Text(), nullable=False),
        sa.Column("line_text", sa.Text(), nullable=False),
        sa.Column("selection_id", sa.Text(), nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["reviewers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["revisions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("row_approvals", schema=None) as batch_op:
        batch_op.create_index("ix_row_approvals_review_reviewer", ["review_id", "reviewer_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_row_approvals_selection_id"), ["selection_id"], unique=False)

    op.create_table(
        "unit_snapshots",
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("old_path", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column("base_hash", sa.Text(), nullable=True),
        sa.Column("head_hash", sa.Text(), nullable=True),
        sa.Column("base_text", sa.Text(), nullable=True),
        sa.Column("head_text", sa.Text(), nullable=True),
        sa.Column("base_lines", sa.JSON(), nullable=False),
        sa.Column("head_lines", sa.JSON(), nullable=False),
        sa.Column("base_start", sa.Integer(), nullable=True),
        sa.Column("base_end", sa.Integer(), nullable=True),
        sa.Column("head_start", sa.Integer(), nullable=True),
        sa.Column("head_end", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["revisions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("unit_snapshots", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_unit_snapshots_revision_id"), ["revision_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("unit_snapshots", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_unit_snapshots_revision_id"))

    op.drop_table("unit_snapshots")
    with op.batch_alter_table("row_approvals", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_row_approvals_selection_id"))
        batch_op.drop_index("ix_row_approvals_review_reviewer")

    op.drop_table("row_approvals")
    with op.batch_alter_table("review_sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_review_sessions_review_id"))

    op.drop_table("review_sessions")
    with op.batch_alter_table("approvals", schema=None) as batch_op:
        batch_op.drop_index("ix_approvals_review_reviewer")

    op.drop_table("approvals")
    with op.batch_alter_table("revisions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_revisions_review_id"))

    op.drop_table("revisions")
    with op.batch_alter_table("reviews", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_reviews_repo_id"))

    op.drop_table("reviews")
    op.drop_table("reviewers")
    with op.batch_alter_table("repos", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_repos_root_commit"))

    op.drop_table("repos")
    op.drop_table("parsed_blobs")
