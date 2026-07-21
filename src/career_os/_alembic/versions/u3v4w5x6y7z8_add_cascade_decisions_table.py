"""Add cascade_decisions table for the confidence-routed cascade (G-1338, finding K).

Revision ID: u3v4w5x6y7z8
Revises: t2u3v4w5x6y7
Create Date: 2026-07-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "u3v4w5x6y7z8"
down_revision: str | None = "t2u3v4w5x6y7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cascade_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("scored_job_id", sa.Integer(), nullable=True),
        sa.Column("discovered_job_id", sa.Integer(), nullable=True),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("would_skip", sa.Boolean(), nullable=False),
        sa.Column("embedding_similarity", sa.Float(), nullable=True),
        sa.Column("embedding_available", sa.Boolean(), nullable=False),
        sa.Column("embedding_votes_reject", sa.Boolean(), nullable=False),
        sa.Column("lexical_overlap", sa.Float(), nullable=True),
        sa.Column("lexical_available", sa.Boolean(), nullable=False),
        sa.Column("lexical_votes_reject", sa.Boolean(), nullable=False),
        sa.Column("esco_overlap", sa.Float(), nullable=True),
        sa.Column("esco_available", sa.Boolean(), nullable=False),
        sa.Column("esco_votes_reject", sa.Boolean(), nullable=False),
        sa.Column("llm_fit_score", sa.Float(), nullable=True),
        sa.Column("llm_quadrant", sa.String(length=20), nullable=True),
        sa.Column("reject_fit_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["scored_job_id"], ["scored_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["discovered_job_id"], ["discovered_jobs.id"]),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cascade_decisions_profile_id"),
        "cascade_decisions",
        ["profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cascade_decisions_scored_job_id"),
        "cascade_decisions",
        ["scored_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cascade_decisions_discovered_job_id"),
        "cascade_decisions",
        ["discovered_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cascade_decisions_application_id"),
        "cascade_decisions",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cascade_decisions_mode"),
        "cascade_decisions",
        ["mode"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cascade_decisions_action"),
        "cascade_decisions",
        ["action"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cascade_decisions_action"), table_name="cascade_decisions")
    op.drop_index(op.f("ix_cascade_decisions_mode"), table_name="cascade_decisions")
    op.drop_index(op.f("ix_cascade_decisions_application_id"), table_name="cascade_decisions")
    op.drop_index(op.f("ix_cascade_decisions_discovered_job_id"), table_name="cascade_decisions")
    op.drop_index(op.f("ix_cascade_decisions_scored_job_id"), table_name="cascade_decisions")
    op.drop_index(op.f("ix_cascade_decisions_profile_id"), table_name="cascade_decisions")
    op.drop_table("cascade_decisions")
