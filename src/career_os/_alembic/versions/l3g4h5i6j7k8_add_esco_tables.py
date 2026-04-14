"""Add ESCO skill taxonomy tables and esco_uri columns.

Adds:
- esco_skills: cached ESCO v1.2 taxonomy (~14K rows), loaded by scripts/load_esco_data.py
- skill_mappings: raw skill text → ESCO URI cache to avoid repeated normalization
- skills.esco_uri: canonical ESCO URI for each profile skill
- job_requirements.esco_uri: canonical ESCO URI for each JD keyword (enables deterministic matching)

Revision ID: l3g4h5i6j7k8
Revises: k2f3g4h5i6j7
Create Date: 2026-04-14 12:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l3g4h5i6j7k8"
down_revision: Union[str, None] = "k2f3g4h5i6j7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- esco_skills table ---
    op.create_table(
        "esco_skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("concept_uri", sa.String(length=500), nullable=False),
        sa.Column("preferred_label", sa.String(length=500), nullable=False),
        sa.Column("alt_labels", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("skill_type", sa.String(length=100), nullable=True),
        sa.Column("isco_group", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concept_uri", name="uq_esco_skills_concept_uri"),
    )
    op.create_index("ix_esco_skills_concept_uri", "esco_skills", ["concept_uri"])
    op.create_index("ix_esco_skills_preferred_label", "esco_skills", ["preferred_label"])

    # --- skill_mappings table ---
    op.create_table(
        "skill_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("raw_text", sa.String(length=500), nullable=False),
        sa.Column("esco_uri", sa.String(length=500), nullable=True),
        sa.Column("preferred_label", sa.String(length=500), nullable=True),
        sa.Column("match_method", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_text", name="uq_skill_mappings_raw_text"),
    )
    op.create_index("ix_skill_mappings_raw_text", "skill_mappings", ["raw_text"])

    # --- esco_uri column on skills ---
    op.add_column("skills", sa.Column("esco_uri", sa.String(length=500), nullable=True))
    op.create_index("ix_skills_esco_uri", "skills", ["esco_uri"])

    # --- esco_uri column on job_requirements ---
    op.add_column("job_requirements", sa.Column("esco_uri", sa.String(length=500), nullable=True))
    op.create_index("ix_job_requirements_esco_uri", "job_requirements", ["esco_uri"])


def downgrade() -> None:
    op.drop_index("ix_job_requirements_esco_uri", table_name="job_requirements")
    op.drop_column("job_requirements", "esco_uri")

    op.drop_index("ix_skills_esco_uri", table_name="skills")
    op.drop_column("skills", "esco_uri")

    op.drop_index("ix_skill_mappings_raw_text", table_name="skill_mappings")
    op.drop_table("skill_mappings")

    op.drop_index("ix_esco_skills_preferred_label", table_name="esco_skills")
    op.drop_index("ix_esco_skills_concept_uri", table_name="esco_skills")
    op.drop_table("esco_skills")
