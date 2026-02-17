"""alerts v2 schema and trigger history

Revision ID: 20260217_0004
Revises: 20260217_0003
Create Date: 2026-02-17 14:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260217_0004'
down_revision: Union[str, None] = '20260217_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    with op.batch_alter_table('price_alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('instrument_type', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('source', sa.String(length=16), nullable=False, server_default='manual'))
        batch_op.add_column(
            sa.Column('condition', sa.String(length=32), nullable=False, server_default='price_above')
        )
        batch_op.add_column(sa.Column('threshold', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('one_shot', sa.Boolean(), nullable=False, server_default=sa.text('false')))
        batch_op.add_column(sa.Column('cooldown_seconds', sa.Integer(), nullable=False, server_default='60'))
        batch_op.add_column(sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('last_triggered_price', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('last_triggered_value', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('last_trigger_source', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('last_seen_price', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('last_condition_state', sa.Boolean(), nullable=True))

    op.execute(
        """
        UPDATE price_alerts
        SET
            source = 'watchlist',
            condition = CASE
                WHEN direction = 'below' THEN 'price_below'
                ELSE 'price_above'
            END,
            threshold = COALESCE(target_price, 0),
            one_shot = false,
            cooldown_seconds = 60,
            last_condition_state = false
        """
    )

    with op.batch_alter_table('price_alerts', schema=None) as batch_op:
        batch_op.alter_column('watchlist_item_id', existing_type=sa.Integer(), nullable=True)
        batch_op.create_index('ix_price_alerts_condition', ['condition'], unique=False)
        batch_op.create_index('ix_price_alerts_enabled', ['enabled'], unique=False)
        batch_op.create_index('ix_price_alerts_last_triggered_at', ['last_triggered_at'], unique=False)
        batch_op.drop_constraint('uq_price_alert_watchlist_item_id', type_='unique')
        batch_op.drop_column('direction')
        batch_op.drop_column('target_price')

    op.create_table(
        'alert_trigger_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('condition', sa.String(length=32), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('trigger_price', sa.Float(), nullable=False),
        sa.Column('trigger_value', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=32), nullable=True),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['alert_id'], ['price_alerts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_alert_trigger_events_alert_id', 'alert_trigger_events', ['alert_id'], unique=False)
    op.create_index('ix_alert_trigger_events_symbol', 'alert_trigger_events', ['symbol'], unique=False)
    op.create_index('ix_alert_trigger_events_triggered_at', 'alert_trigger_events', ['triggered_at'], unique=False)



def downgrade() -> None:
    op.drop_index('ix_alert_trigger_events_triggered_at', table_name='alert_trigger_events')
    op.drop_index('ix_alert_trigger_events_symbol', table_name='alert_trigger_events')
    op.drop_index('ix_alert_trigger_events_alert_id', table_name='alert_trigger_events')
    op.drop_table('alert_trigger_events')

    with op.batch_alter_table('price_alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('target_price', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('direction', sa.String(length=8), nullable=False, server_default='above'))

    op.execute(
        """
        UPDATE price_alerts
        SET
            direction = CASE
                WHEN condition IN ('price_below', 'crosses_below', 'percent_move_down') THEN 'below'
                ELSE 'above'
            END,
            target_price = threshold
        """
    )

    with op.batch_alter_table('price_alerts', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_price_alert_watchlist_item_id', ['watchlist_item_id'])
        batch_op.alter_column('watchlist_item_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_index('ix_price_alerts_last_triggered_at')
        batch_op.drop_index('ix_price_alerts_enabled')
        batch_op.drop_index('ix_price_alerts_condition')
        batch_op.drop_column('last_condition_state')
        batch_op.drop_column('last_seen_price')
        batch_op.drop_column('last_trigger_source')
        batch_op.drop_column('last_triggered_value')
        batch_op.drop_column('last_triggered_price')
        batch_op.drop_column('last_triggered_at')
        batch_op.drop_column('cooldown_seconds')
        batch_op.drop_column('one_shot')
        batch_op.drop_column('threshold')
        batch_op.drop_column('condition')
        batch_op.drop_column('source')
        batch_op.drop_column('instrument_type')
