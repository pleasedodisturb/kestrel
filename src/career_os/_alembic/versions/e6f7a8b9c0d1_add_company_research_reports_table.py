"""Add company_research_reports table.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-03-14 04:00:00.000000

"""

from typing import Union
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_research_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("profiles.id"),
            nullable=False,
        ),
        sa.Column("company_name", sa.String(500), nullable=False),
        sa.Column("report_json", sa.Text(), nullable=True),
        sa.Column("values_alignment_score", sa.Float(), nullable=True),
        sa.Column("industry_segment", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_company_research_reports_profile_id",
        "company_research_reports",
        ["profile_id"],
    )
    op.create_index(
        "ix_company_research_reports_company_name",
        "company_research_reports",
        ["company_name"],
    )


def downgrade() -> None:
    op.drop_table("company_research_reports")
