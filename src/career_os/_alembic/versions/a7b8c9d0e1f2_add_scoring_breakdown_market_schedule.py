"""add score_breakdown, dream_companies, market_refresh, schedule columns

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-03-13 23:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix 1: Add score_breakdown JSON column to scored_jobs
    with op.batch_alter_table("scored_jobs") as batch_op:
        batch_op.add_column(
            sa.Column("score_breakdown", sa.Text(), nullable=True)
        )

    # Fix 4: Add dream_companies JSON column to profiles
    with op.batch_alter_table("profiles") as batch_op:
        batch_op.add_column(
            sa.Column("dream_companies", sa.Text(), nullable=True)
        )

    # Fix 5: Add last_market_refreshed_at to profiles
    with op.batch_alter_table("profiles") as batch_op:
        batch_op.add_column(
            sa.Column(
                "last_market_refreshed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    # Fix 7: Add cadence and next_run columns to search_profiles
    with op.batch_alter_table("search_profiles") as batch_op:
        batch_op.add_column(
            sa.Column("cadence", sa.String(50), nullable=True)
        )
        batch_op.add_column(
            sa.Column("next_run", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("search_profiles") as batch_op:
        batch_op.drop_column("next_run")
        batch_op.drop_column("cadence")

    with op.batch_alter_table("profiles") as batch_op:
        batch_op.drop_column("last_market_refreshed_at")
        batch_op.drop_column("dream_companies")

    with op.batch_alter_table("scored_jobs") as batch_op:
        batch_op.drop_column("score_breakdown")
