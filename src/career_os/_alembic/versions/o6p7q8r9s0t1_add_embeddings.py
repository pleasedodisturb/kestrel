"""Add embeddings table and embedding_similarity column (Epic 4 / G-272).

Revision ID: o6p7q8r9s0t1
Revises: l3m4n5o6p7q8
Create Date: 2026-04-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o6p7q8r9s0t1"
down_revision: Union[str, None] = "l3m4n5o6p7q8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- embeddings table ---
    op.create_table(
        "embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("vector", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "entity_id", "model_name", name="uq_embedding_entity"),
    )
    op.create_index(
        op.f("ix_embeddings_entity_type"), "embeddings", ["entity_type"], unique=False
    )
    op.create_index(
        op.f("ix_embeddings_entity_id"), "embeddings", ["entity_id"], unique=False
    )

    # --- embedding_similarity column on discovered_jobs ---
    op.add_column(
        "discovered_jobs",
        sa.Column("embedding_similarity", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("discovered_jobs", "embedding_similarity")
    op.drop_index(op.f("ix_embeddings_entity_id"), table_name="embeddings")
    op.drop_index(op.f("ix_embeddings_entity_type"), table_name="embeddings")
    op.drop_table("embeddings")
