"""add scoring enhancement columns to scored_jobs

Adds columns required by the pre-launch scoring enhancement sprint (G-213):

* ``red_flags`` — JSON array of rule-based red flags (G-216)
* ``ats_keywords`` — JSON array of ATS keywords extracted per JD (G-218)
* ``dim_technical_fit`` / ``dim_seniority_alignment`` /
  ``dim_compensation_fit`` / ``dim_location_fit`` /
  ``dim_career_trajectory`` / ``dim_company_fit`` — 6 dimensional
  sub-scores (G-217)

All columns are nullable; existing rows get NULL and no backfill is
required.

Revision ID: b8d3e7a2c914
Revises: eac8c4fc464e
Create Date: 2026-04-11 17:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d3e7a2c914"
down_revision: Union[str, Sequence[str], None] = "eac8c4fc464e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add scoring enhancement columns to scored_jobs."""
    with op.batch_alter_table("scored_jobs") as batch_op:
        batch_op.add_column(sa.Column("red_flags", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ats_keywords", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("dim_technical_fit", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("dim_seniority_alignment", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("dim_compensation_fit", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("dim_location_fit", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("dim_career_trajectory", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("dim_company_fit", sa.Float(), nullable=True))


def downgrade() -> None:
    """Drop the scoring enhancement columns."""
    with op.batch_alter_table("scored_jobs") as batch_op:
        batch_op.drop_column("dim_company_fit")
        batch_op.drop_column("dim_career_trajectory")
        batch_op.drop_column("dim_location_fit")
        batch_op.drop_column("dim_compensation_fit")
        batch_op.drop_column("dim_seniority_alignment")
        batch_op.drop_column("dim_technical_fit")
        batch_op.drop_column("ats_keywords")
        batch_op.drop_column("red_flags")
