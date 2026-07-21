"""Add notification_preferences and notification_logs tables for Pushover integration.

Revision ID: j1e2f3g4h5i6
Revises: i0d1e2f3g4h5
Create Date: 2026-03-14 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j1e2f3g4h5i6"
down_revision: Union[str, None] = "i0d1e2f3g4h5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create notification_preferences and notification_logs tables."""
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("follow_up_reminders", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("ghost_alerts", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("discovery_alerts", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("interview_reminders", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("quiet_hours_start", sa.Integer(), nullable=True),
        sa.Column("quiet_hours_end", sa.Integer(), nullable=True),
        sa.Column(
            "interview_lead_time_minutes",
            sa.Integer(),
            nullable=False,
            server_default="1440",
        ),
        sa.Column(
            "discovery_score_threshold",
            sa.Integer(),
            nullable=False,
            server_default="7",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_preferences_profile_id",
        "notification_preferences",
        ["profile_id"],
    )

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="sent"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_logs_profile_id",
        "notification_logs",
        ["profile_id"],
    )


def downgrade() -> None:
    """Drop notification tables."""
    op.drop_index("ix_notification_logs_profile_id", table_name="notification_logs")
    op.drop_table("notification_logs")
    op.drop_index(
        "ix_notification_preferences_profile_id",
        table_name="notification_preferences",
    )
    op.drop_table("notification_preferences")
