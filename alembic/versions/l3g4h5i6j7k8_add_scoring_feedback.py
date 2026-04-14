"""Add scoring_feedback table for user feedback loop (Epic 6 / G-274).

Revision ID: l3g4h5i6j7k8
Revises: k2f3g4h5i6j7
Create Date: 2026-04-14 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l3g4h5i6j7k8"
down_revision: Union[str, None] = "k2f3g4h5i6j7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scoring_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scored_job_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=50), nullable=False),
        sa.Column("user_score", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("original_fit_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["scored_job_id"], ["scored_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_scoring_feedback_profile_id"), "scoring_feedback", ["profile_id"], unique=False
    )
    op.create_index(
        op.f("ix_scoring_feedback_scored_job_id"),
        "scoring_feedback",
        ["scored_job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_scoring_feedback_scored_job_id"), table_name="scoring_feedback")
    op.drop_index(op.f("ix_scoring_feedback_profile_id"), table_name="scoring_feedback")
    op.drop_table("scoring_feedback")
