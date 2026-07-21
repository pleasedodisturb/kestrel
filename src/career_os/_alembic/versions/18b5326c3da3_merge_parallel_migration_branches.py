"""merge parallel migration branches

Revision ID: 18b5326c3da3
Revises: g397_ai_usage, r9s0t1u2v3w4
Create Date: 2026-04-21 12:52:54.023006

"""

from typing import Union
from collections.abc import Sequence


# revision identifiers, used by Alembic.
revision: str = "18b5326c3da3"
down_revision: Union[str, Sequence[str], None] = ("g397_ai_usage", "r9s0t1u2v3w4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
