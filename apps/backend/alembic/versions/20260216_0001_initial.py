"""initial

Revision ID: 20260216_0001
Revises:
Create Date: 2026-02-16 23:45:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260216_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text('SELECT 1'))


def downgrade() -> None:
    op.execute(sa.text('SELECT 1'))
