from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("unit_descriptions", schema=None) as batch_op:
        batch_op.alter_column("description", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM unit_descriptions WHERE description IS NULL")
    with op.batch_alter_table("unit_descriptions", schema=None) as batch_op:
        batch_op.alter_column("description", existing_type=sa.Text(), nullable=False)
