from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("forge_links", schema=None) as batch_op:
        batch_op.add_column(sa.Column("title", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("author", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("state", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("synced_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("forge_links", schema=None) as batch_op:
        batch_op.drop_column("synced_at")
        batch_op.drop_column("state")
        batch_op.drop_column("url")
        batch_op.drop_column("author")
        batch_op.drop_column("title")
