"""add parent_event_id to calendar_events

Revision ID: eac8c4fc464e
Revises: k2f3g4h5i6j7
Create Date: 2026-03-14 10:35:45.464157

"""

from typing import Union
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "eac8c4fc464e"
down_revision: Union[str, Sequence[str], None] = "k2f3g4h5i6j7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("calendar_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_event_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_calendar_events_parent_event_id"), ["parent_event_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_calendar_events_parent_event_id",
            "calendar_events",
            ["parent_event_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("calendar_events", schema=None) as batch_op:
        batch_op.drop_constraint("fk_calendar_events_parent_event_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_calendar_events_parent_event_id"))
        batch_op.drop_column("parent_event_id")
