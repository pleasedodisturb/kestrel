"""add is_demo column to applications

Revision ID: r9s0t1u2v3w4
Revises: q8r9s0t1u2v3
Create Date: 2026-04-20 14:00:00.000000

"""

from typing import Union
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "r9s0t1u2v3w4"
down_revision: Union[str, Sequence[str], None] = "q8r9s0t1u2v3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_demo Boolean column to applications table."""
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_demo", sa.Boolean(), server_default=sa.text("0"), nullable=False)
        )


def downgrade() -> None:
    """Remove is_demo column from applications table."""
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_column("is_demo")
