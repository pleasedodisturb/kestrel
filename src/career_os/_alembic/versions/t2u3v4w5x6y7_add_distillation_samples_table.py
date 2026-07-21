"""Add distillation_samples table for distillation-label logging (G-1338, finding M).

Revision ID: t2u3v4w5x6y7
Revises: s1t2u3v4w5x6
Create Date: 2026-07-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "t2u3v4w5x6y7"
down_revision: str | None = "s1t2u3v4w5x6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "distillation_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("scored_job_id", sa.Integer(), nullable=True),
        sa.Column("discovered_job_id", sa.Integer(), nullable=True),
        sa.Column("fit_score", sa.Float(), nullable=False),
        sa.Column("desire_score", sa.Float(), nullable=True),
        sa.Column("quadrant", sa.String(length=20), nullable=True),
        sa.Column("signals", sa.Text(), nullable=True),
        sa.Column("rubric_version", sa.String(length=20), nullable=True),
        sa.Column("feedback_direction", sa.String(length=50), nullable=True),
        sa.Column("feedback_user_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(
            ["scored_job_id"], ["scored_jobs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["discovered_job_id"], ["discovered_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_distillation_samples_profile_id"),
        "distillation_samples",
        ["profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_distillation_samples_scored_job_id"),
        "distillation_samples",
        ["scored_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_distillation_samples_discovered_job_id"),
        "distillation_samples",
        ["discovered_job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_distillation_samples_discovered_job_id"), table_name="distillation_samples"
    )
    op.drop_index(
        op.f("ix_distillation_samples_scored_job_id"), table_name="distillation_samples"
    )
    op.drop_index(op.f("ix_distillation_samples_profile_id"), table_name="distillation_samples")
    op.drop_table("distillation_samples")
