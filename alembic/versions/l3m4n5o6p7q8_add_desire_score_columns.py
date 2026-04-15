"""add desire_score columns to scored_jobs

Adds columns for the dual-score architecture (G-275):

* ``desire_score`` — 0-10 float measuring "how much would the user want this job?"
* ``desire_score_method`` — tracking which computation method was used
  ("derived" or "ai_generated")
* ``desire_reasoning`` — separate reasoning text for desire score (Option B only)

All columns are nullable; existing rows get NULL and no backfill is required.

Revision ID: l3m4n5o6p7q8
Revises: n5o6p7q8r9s0
Create Date: 2026-04-14 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l3m4n5o6p7q8"
down_revision: str | Sequence[str] | None = "n5o6p7q8r9s0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add desire_score columns to scored_jobs."""
    with op.batch_alter_table("scored_jobs") as batch_op:
        batch_op.add_column(sa.Column("desire_score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("desire_score_method", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("desire_reasoning", sa.Text(), nullable=True))


def downgrade() -> None:
    """Drop the desire_score columns."""
    with op.batch_alter_table("scored_jobs") as batch_op:
        batch_op.drop_column("desire_reasoning")
        batch_op.drop_column("desire_score_method")
        batch_op.drop_column("desire_score")
