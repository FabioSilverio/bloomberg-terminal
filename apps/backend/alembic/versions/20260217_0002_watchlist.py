"""watchlist table

Revision ID: 20260217_0002
Revises: 20260216_0001
Create Date: 2026-02-17 10:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260217_0002'
down_revision: Union[str, None] = '20260216_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'watchlist_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('display_symbol', sa.String(length=32), nullable=False),
        sa.Column('provider_symbol', sa.String(length=32), nullable=False),
        sa.Column('instrument_type', sa.String(length=16), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', name='uq_watchlist_items_symbol'),
    )
    op.create_index('ix_watchlist_items_position', 'watchlist_items', ['position'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_watchlist_items_position', table_name='watchlist_items')
    op.drop_table('watchlist_items')
