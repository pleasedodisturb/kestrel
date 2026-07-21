"""Add ai_usage_log table for token cost tracking.

Revision ID: g397_ai_usage
Revises: p7q8r9s0t1u2
Create Date: 2026-04-20
"""

from typing import Union
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g397_ai_usage"
down_revision: Union[str, Sequence[str], None] = "p7q8r9s0t1u2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the ai_usage_log table."""
    op.create_table(
        "ai_usage_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("feature", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_creation_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ai_usage_log", schema=None) as batch_op:
        batch_op.create_index("ix_ai_usage_log_timestamp", ["timestamp"])
        batch_op.create_index("ix_ai_usage_log_provider", ["provider"])
        batch_op.create_index("ix_ai_usage_log_feature", ["feature"])


def downgrade() -> None:
    """Drop the ai_usage_log table."""
    with op.batch_alter_table("ai_usage_log", schema=None) as batch_op:
        batch_op.drop_index("ix_ai_usage_log_timestamp")
        batch_op.drop_index("ix_ai_usage_log_provider")
        batch_op.drop_index("ix_ai_usage_log_feature")
    op.drop_table("ai_usage_log")
