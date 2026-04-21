"""add salary_range and experience_level to profiles

Revision ID: q8r9s0t1u2v3
Revises: e68f373345cd
Create Date: 2026-04-20 13:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'q8r9s0t1u2v3'
down_revision: Union[str, Sequence[str], None] = 'e68f373345cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add salary_range and experience_level columns to profiles table."""
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('salary_range', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('experience_level', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Remove salary_range and experience_level columns from profiles table."""
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.drop_column('experience_level')
        batch_op.drop_column('salary_range')
