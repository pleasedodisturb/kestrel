"""add gap_id and started_at to learning_resources

Revision ID: b192ca99adc9
Revises: a1b2c3d4e5f6
Create Date: 2026-03-13 15:25:01.704693

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b192ca99adc9'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('learning_resources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gap_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_learning_resources_gap_id'), ['gap_id'], unique=False)
        batch_op.create_foreign_key('fk_learning_resources_gap_id', 'job_requirements', ['gap_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('learning_resources', schema=None) as batch_op:
        batch_op.drop_constraint('fk_learning_resources_gap_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_learning_resources_gap_id'))
        batch_op.drop_column('started_at')
        batch_op.drop_column('gap_id')
