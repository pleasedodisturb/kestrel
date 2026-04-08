"""add profile_id to discovered_job dedup constraint

Revision ID: f1a2b3c4d5e6
Revises: 07cca291f71f
Create Date: 2026-03-13 22:10:00.000000

"""

from typing import Union
from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "07cca291f71f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add profile_id to the discovered_job dedup unique constraint."""
    with op.batch_alter_table("discovered_jobs", schema=None) as batch_op:
        batch_op.drop_constraint("uq_discovered_job_dedup", type_="unique")
        batch_op.create_unique_constraint(
            "uq_discovered_job_dedup",
            [
                "profile_id",
                "title_normalized",
                "company_normalized",
                "location_normalized",
            ],
        )


def downgrade() -> None:
    """Remove profile_id from the dedup constraint."""
    with op.batch_alter_table("discovered_jobs", schema=None) as batch_op:
        batch_op.drop_constraint("uq_discovered_job_dedup", type_="unique")
        batch_op.create_unique_constraint(
            "uq_discovered_job_dedup",
            [
                "title_normalized",
                "company_normalized",
                "location_normalized",
            ],
        )
