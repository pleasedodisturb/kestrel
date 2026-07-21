"""Add warn_filings table for WARN Act layoff data (Epic 9 / G-277).

Re-parented onto u3v4w5x6y7z8 by G-1350. This revision only ever existed in the
stale packaged _alembic copy (never in the authoritative root chain), so it was
never applied anywhere and `warn_filings` was missing from every migrated
database -- while models/warn.py, cli/warn.py and the WARN red-flag rule all
query it. Its original parent (l3g4h5i6j7k8, an ESCO duplicate) is redundant:
e68f373345cd already creates esco_skills/skill_mappings in the canonical chain.

Revision ID: m4n5o6p7q8r9
Revises: u3v4w5x6y7z8
Create Date: 2026-04-14 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m4n5o6p7q8r9"
down_revision: Union[str, None] = "u3v4w5x6y7z8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create warn_filings table."""
    op.create_table(
        "warn_filings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_name", sa.String(length=500), nullable=False),
        sa.Column("company_name_normalized", sa.String(length=500), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("employees_affected", sa.Integer(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("notice_date", sa.Date(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_warn_filings_company_name"),
        "warn_filings",
        ["company_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_warn_filings_company_name_normalized"),
        "warn_filings",
        ["company_name_normalized"],
        unique=False,
    )
    op.create_index(
        op.f("ix_warn_filings_state"),
        "warn_filings",
        ["state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_warn_filings_notice_date"),
        "warn_filings",
        ["notice_date"],
        unique=False,
    )


def downgrade() -> None:
    """Drop warn_filings table."""
    op.drop_index(op.f("ix_warn_filings_notice_date"), table_name="warn_filings")
    op.drop_index(op.f("ix_warn_filings_state"), table_name="warn_filings")
    op.drop_index(op.f("ix_warn_filings_company_name_normalized"), table_name="warn_filings")
    op.drop_index(op.f("ix_warn_filings_company_name"), table_name="warn_filings")
    op.drop_table("warn_filings")
