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
    """Forward-only: the feature is gone, no restore path is provided."""
    raise NotImplementedError(
        "time_sessions was dropped as part of the TimingsApp removal (d2e5a7f1b9c3)."
    )
