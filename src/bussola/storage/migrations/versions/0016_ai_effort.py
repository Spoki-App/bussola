from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESULT_KEY = ("task", "prompt_version", "instructions_hash", "provider", "model", "endpoint", "content_hash")
COPY_WITH_EFFORT = (
    "INSERT INTO ai_results_new (task, prompt_version, instructions_hash, provider, model, endpoint, content_hash, result, created_at, effort) "
    "SELECT task, prompt_version, instructions_hash, provider, model, endpoint, content_hash, result, created_at, '' FROM ai_results"
)
COPY_WITHOUT_EFFORT = (
    "INSERT INTO ai_results_new (task, prompt_version, instructions_hash, provider, model, endpoint, content_hash, result, created_at) "
    "SELECT task, prompt_version, instructions_hash, provider, model, endpoint, content_hash, result, created_at FROM ai_results WHERE effort = ''"
)
SHOWN_RESULTS = ("unit_descriptions", "ai_review_runs", "ai_chat_messages")


def upgrade() -> None:
    _copy_results(with_effort=True)
    for table in SHOWN_RESULTS:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("effort", sa.Text(), nullable=True))


def downgrade() -> None:
    for table in SHOWN_RESULTS:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("effort")
    _copy_results(with_effort=False)


def _copy_results(*, with_effort: bool) -> None:
    key = (*RESULT_KEY, "effort") if with_effort else RESULT_KEY
    op.create_table(
        "ai_results_new",
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("instructions_hash", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        *([sa.Column("effort", sa.Text(), nullable=False)] if with_effort else []),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint(*key),
    )
    op.execute(COPY_WITH_EFFORT if with_effort else COPY_WITHOUT_EFFORT)
    op.drop_table("ai_results")
    op.rename_table("ai_results_new", "ai_results")
