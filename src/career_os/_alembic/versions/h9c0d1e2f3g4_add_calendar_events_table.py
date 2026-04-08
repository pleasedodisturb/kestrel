"""Add calendar_events table.

Revision ID: h9c0d1e2f3g4
Revises: g8b9c0d1e2f3
Create Date: 2026-03-14 08:00:00.000000

"""

from typing import Union
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h9c0d1e2f3g4"
down_revision: Union[str, None] = "g8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("follow_up_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=500), nullable=True),
        sa.Column("interview_type", sa.String(length=100), nullable=True),
        sa.Column("meeting_link", sa.Text(), nullable=True),
        sa.Column("prep_notes", sa.Text(), nullable=True),
        sa.Column(
            "reminder_minutes_before",
            sa.Integer(),
            nullable=True,
            server_default="1440",
        ),
        sa.Column("uid", sa.String(length=255), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_calendar_events_profile_id"),
        "calendar_events",
        ["profile_id"],
    )
    op.create_index(
        op.f("ix_calendar_events_application_id"),
        "calendar_events",
        ["application_id"],
    )
    op.create_index(
        op.f("ix_calendar_events_follow_up_id"),
        "calendar_events",
        ["follow_up_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_calendar_events_follow_up_id"),
        table_name="calendar_events",
    )
    op.drop_index(
        op.f("ix_calendar_events_application_id"),
        table_name="calendar_events",
    )
    op.drop_index(
        op.f("ix_calendar_events_profile_id"),
        table_name="calendar_events",
    )
    op.drop_table("calendar_events")
