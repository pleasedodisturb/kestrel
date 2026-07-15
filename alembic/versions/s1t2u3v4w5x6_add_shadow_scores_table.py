"""Add shadow_scores table for scoring shadow-mode (G-1336, finding I).

Revision ID: s1t2u3v4w5x6
Revises: 18b5326c3da3
Create Date: 2026-07-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "s1t2u3v4w5x6"
down_revision: str | None = "18b5326c3da3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shadow_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("scored_job_id", sa.Integer(), nullable=True),
        sa.Column("discovered_job_id", sa.Integer(), nullable=True),
        sa.Column("variant", sa.String(length=100), nullable=False),
        sa.Column("fit_score", sa.Float(), nullable=False),
        sa.Column("desire_score", sa.Float(), nullable=True),
        sa.Column("quadrant", sa.String(length=20), nullable=True),
        sa.Column("primary_fit_score", sa.Float(), nullable=True),
        sa.Column("dimensional_scores", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(
            ["scored_job_id"], ["scored_jobs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["discovered_job_id"], ["discovered_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_shadow_scores_profile_id"), "shadow_scores", ["profile_id"], unique=False
    )
    op.create_index(
        op.f("ix_shadow_scores_scored_job_id"), "shadow_scores", ["scored_job_id"], unique=False
    )
    op.create_index(
        op.f("ix_shadow_scores_discovered_job_id"),
        "shadow_scores",
        ["discovered_job_id"],
        unique=False,
    )
    op.create_index(op.f("ix_shadow_scores_variant"), "shadow_scores", ["variant"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_shadow_scores_variant"), table_name="shadow_scores")
    op.drop_index(op.f("ix_shadow_scores_discovered_job_id"), table_name="shadow_scores")
    op.drop_index(op.f("ix_shadow_scores_scored_job_id"), table_name="shadow_scores")
    op.drop_index(op.f("ix_shadow_scores_profile_id"), table_name="shadow_scores")
    op.drop_table("shadow_scores")
