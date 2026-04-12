"""drop time_sessions table (TimingsApp integration removed)

Forward-only cleanup migration for the TimingsApp removal. Drops
the ``time_sessions`` table along with its profile_id index and
cleans any lingering ``integration_configs`` row whose ``name``
field equals ``timingsapp``.

Revision ID: d2e5a7f1b9c3
Revises: b8d3e7a2c914
Create Date: 2026-04-11 21:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2e5a7f1b9c3"
down_revision: Union[str, Sequence[str], None] = "b8d3e7a2c914"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PURGE_TIMINGSAPP_CONFIG = sa.text("DELETE FROM integration_configs WHERE name = 'timingsapp'")


def upgrade() -> None:
    """Drop the time_sessions table and purge orphaned integration_configs rows."""
    op.drop_index(op.f("ix_time_sessions_profile_id"), table_name="time_sessions")
    op.drop_table("time_sessions")
    op.execute(_PURGE_TIMINGSAPP_CONFIG)


def downgrade() -> None:
    """Recreate time_sessions table (schema from i0d1e2f3g4h5)."""
    op.create_table(
        "time_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("activity_name", sa.String(length=500), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("timingsapp_entry_id", sa.String(length=255), nullable=True),
        sa.Column("timingsapp_project", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_time_sessions_profile_id"),
        "time_sessions",
        ["profile_id"],
        unique=False,
    )
