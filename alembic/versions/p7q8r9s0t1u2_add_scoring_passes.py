"""add scoring_passes to scored_jobs

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-04-15 00:00:00.000000

Adds ``scoring_passes`` column to ``scored_jobs`` to track whether a job used
single-pass or 2-pass (borderline) scoring (Epic 5 / G-273).
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "p7q8r9s0t1u2"
down_revision = "o6p7q8r9s0t1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scored_jobs",
        sa.Column("scoring_passes", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("scored_jobs", "scoring_passes")
