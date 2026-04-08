"""Add voice_sessions and voice_messages tables for voice discussion mode.

Revision ID: k2f3g4h5i6j7
Revises: j1e2f3g4h5i6
Create Date: 2026-03-14 14:00:00.000000

"""

from typing import Union
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k2f3g4h5i6j7"
down_revision: Union[str, None] = "j1e2f3g4h5i6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "voice_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("mode", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_voice_sessions_profile_id", "voice_sessions", ["profile_id"])
    op.create_index("ix_voice_sessions_application_id", "voice_sessions", ["application_id"])

    op.create_table(
        "voice_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["voice_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_voice_messages_session_id", "voice_messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_voice_messages_session_id", table_name="voice_messages")
    op.drop_table("voice_messages")
    op.drop_index("ix_voice_sessions_application_id", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_profile_id", table_name="voice_sessions")
    op.drop_table("voice_sessions")
