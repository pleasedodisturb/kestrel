"""Add interview prep tables.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-03-14 00:00:00.000000

"""

from typing import Union
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Interview prep session per application
    op.create_table(
        "interview_prep_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("profiles.id"),
            nullable=False,
        ),
        sa.Column("topics", sa.Text(), nullable=True),  # JSON
        sa.Column("questions", sa.Text(), nullable=True),  # JSON
        sa.Column("total_prep_hours", sa.Float(), nullable=True),
        sa.Column("company_researched", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_interview_prep_sessions_application_id",
        "interview_prep_sessions",
        ["application_id"],
    )
    op.create_index(
        "ix_interview_prep_sessions_profile_id",
        "interview_prep_sessions",
        ["profile_id"],
    )

    # Checklist items for interview prep, with completion tracking
    op.create_table(
        "interview_prep_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("interview_prep_sessions.id"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("profiles.id"),
            nullable=False,
        ),
        sa.Column("item", sa.Text(), nullable=False),
        sa.Column("time_minutes", sa.Integer(), nullable=False),
        sa.Column("priority", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_interview_prep_items_session_id",
        "interview_prep_items",
        ["session_id"],
    )
    op.create_index(
        "ix_interview_prep_items_profile_id",
        "interview_prep_items",
        ["profile_id"],
    )


def downgrade() -> None:
    op.drop_table("interview_prep_items")
    op.drop_table("interview_prep_sessions")
