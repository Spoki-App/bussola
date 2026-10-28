from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("published_comments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("remote_body_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("published_comments", schema=None) as batch_op:
        batch_op.drop_column("remote_body_hash")
