"""add ondelete SET NULL to discovery_run search_profile_id FK

Revision ID: b3c4d5e6f7a8
Revises: a7b8c9d0e1f2
Create Date: 2026-03-14 00:36:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Recreate discovery_runs.search_profile_id FK with ondelete='SET NULL'.

    SQLite doesn't support ALTER CONSTRAINT, so we use batch mode which
    recreates the table behind the scenes.

    Uses naming_convention so batch mode can auto-detect unnamed FKs in
    SQLite (where constraints are typically unnamed).
    """
    naming_convention = {
        "fk": "fk_%(table_name)s_%(column_0_name)s",
    }
    with op.batch_alter_table(
        "discovery_runs",
        naming_convention=naming_convention,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_discovery_runs_search_profile_id",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_discovery_runs_search_profile_id",
            "search_profiles",
            ["search_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    naming_convention = {
        "fk": "fk_%(table_name)s_%(column_0_name)s",
    }
    with op.batch_alter_table(
        "discovery_runs",
        naming_convention=naming_convention,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_discovery_runs_search_profile_id",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_discovery_runs_search_profile_id",
            "search_profiles",
            ["search_profile_id"],
            ["id"],
        )
