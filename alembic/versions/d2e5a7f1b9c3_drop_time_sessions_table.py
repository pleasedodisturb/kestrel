"""Drop time_sessions table (TimingsApp removed).

The TimingsApp integration has been deleted from the codebase in its
entirety. This migration is the runtime cleanup step: drop the
``time_sessions`` table created by ``i0d1e2f3g4h5`` and purge any
``integration_configs`` rows still pointing at the ``timingsapp``
integration name so the settings UI doesn't resurrect a stale panel.

Forward-only — ``downgrade()`` intentionally raises, see below.

Revision ID: d2e5a7f1b9c3
Revises: b8d3e7a2c914
Create Date: 2026-04-11 21:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d2e5a7f1b9c3"
down_revision: str | Sequence[str] | None = "b8d3e7a2c914"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_time_sessions_profile_id", table_name="time_sessions")
    op.drop_table("time_sessions")
    op.execute("DELETE FROM integration_configs WHERE name = 'timingsapp'")


def downgrade() -> None:
    raise NotImplementedError(
        "TimingsApp was removed in d2e5a7f1b9c3; time_sessions is not restorable."
    )
