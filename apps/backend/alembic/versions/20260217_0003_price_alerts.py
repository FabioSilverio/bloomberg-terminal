"""price alerts table

Revision ID: 20260217_0003
Revises: 20260217_0002
Create Date: 2026-02-17 12:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260217_0003'
down_revision: Union[str, None] = '20260217_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'price_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('watchlist_item_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('direction', sa.String(length=8), nullable=False, server_default='above'),
        sa.Column('target_price', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['watchlist_item_id'], ['watchlist_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('watchlist_item_id', name='uq_price_alert_watchlist_item_id'),
    )
    op.create_index('ix_price_alerts_watchlist_item_id', 'price_alerts', ['watchlist_item_id'], unique=False)
    op.create_index('ix_price_alerts_symbol', 'price_alerts', ['symbol'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_price_alerts_symbol', table_name='price_alerts')
    op.drop_index('ix_price_alerts_watchlist_item_id', table_name='price_alerts')
    op.drop_table('price_alerts')
