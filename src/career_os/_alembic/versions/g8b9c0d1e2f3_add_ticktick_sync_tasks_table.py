"""Add ticktick_sync_tasks table.

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-03-14 07:00:00.000000

"""

from typing import Union
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g8b9c0d1e2f3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticktick_sync_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("ticktick_task_id", sa.String(length=255), nullable=False),
        sa.Column("ticktick_project_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="synced",
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ticktick_sync_tasks_profile_id"),
        "ticktick_sync_tasks",
        ["profile_id"],
    )
    op.create_index(
        op.f("ix_ticktick_sync_tasks_ticktick_task_id"),
        "ticktick_sync_tasks",
        ["ticktick_task_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ticktick_sync_tasks_ticktick_task_id"),
        table_name="ticktick_sync_tasks",
    )
    op.drop_index(
        op.f("ix_ticktick_sync_tasks_profile_id"),
        table_name="ticktick_sync_tasks",
    )
    op.drop_table("ticktick_sync_tasks")
