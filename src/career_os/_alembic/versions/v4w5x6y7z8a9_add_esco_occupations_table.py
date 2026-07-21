"""Add esco_occupations table — occupations-pillar cache (G-1351, scoring F5 Phase A).

A first-class occupations taxonomy, separate from the esco_skills cache: the 4a
title→occupation axis was inert in production precisely because there were no
occupation concepts to match against (esco_skills holds skills/competences only).

Source data: ESCO (© European Union), reused under CC BY 4.0
(Commission Decision 2011/833/EU); loaded by scripts/load_esco_occupations.py.

Revision ID: v4w5x6y7z8a9
Revises: m4n5o6p7q8r9
Create Date: 2026-07-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "v4w5x6y7z8a9"
down_revision: str | None = "m4n5o6p7q8r9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "esco_occupations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("concept_uri", sa.String(length=500), nullable=False),
        sa.Column("preferred_label", sa.String(length=500), nullable=False),
        sa.Column("alt_labels", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occupation_code", sa.String(length=50), nullable=True),
        sa.Column("isco_group", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_esco_occupations_concept_uri", "esco_occupations", ["concept_uri"], unique=True
    )
    op.create_index(
        "ix_esco_occupations_preferred_label", "esco_occupations", ["preferred_label"]
    )
    op.create_index("ix_esco_occupations_isco_group", "esco_occupations", ["isco_group"])


def downgrade() -> None:
    op.drop_index("ix_esco_occupations_isco_group", table_name="esco_occupations")
    op.drop_index("ix_esco_occupations_preferred_label", table_name="esco_occupations")
    op.drop_index("ix_esco_occupations_concept_uri", table_name="esco_occupations")
    op.drop_table("esco_occupations")
