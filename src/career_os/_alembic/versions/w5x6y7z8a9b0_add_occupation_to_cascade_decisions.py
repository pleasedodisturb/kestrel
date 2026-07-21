"""Add occupation shadow signal columns to cascade_decisions (G-1351 Phase C).

Revision ID: w5x6y7z8a9b0
Revises: v4w5x6y7z8a9
Create Date: 2026-07-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "w5x6y7z8a9b0"
down_revision: str | None = "v4w5x6y7z8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cascade_decisions",
        sa.Column("occupation_match", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "cascade_decisions",
        sa.Column("occupation_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "cascade_decisions",
        sa.Column(
            "occupation_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "cascade_decisions",
        sa.Column(
            "occupation_votes_reject",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("cascade_decisions", "occupation_votes_reject")
    op.drop_column("cascade_decisions", "occupation_available")
    op.drop_column("cascade_decisions", "occupation_score")
    op.drop_column("cascade_decisions", "occupation_match")
