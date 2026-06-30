"""phase7_session_trim

Revision ID: cc78fb5f456e
Revises: f24c87421d9e
Create Date: 2026-06-30 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cc78fb5f456e"
down_revision: Union[str, Sequence[str], None] = "f24c87421d9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add non-destructive trim window columns to sessions table (Phase 7)."""
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("trim_start_ms", sa.BigInteger(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("trim_end_ms", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    """Remove trim window columns from sessions table."""
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_column("trim_end_ms")
        batch_op.drop_column("trim_start_ms")
