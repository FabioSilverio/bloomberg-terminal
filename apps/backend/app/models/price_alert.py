from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ALERT_CONDITIONS = {
    'price_above',
    'price_below',
    'crosses_above',
    'crosses_below',
    'percent_move_up',
    'percent_move_down',
}


class PriceAlert(Base):
    __tablename__ = 'price_alerts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watchlist_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey('watchlist_items.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    instrument_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default='manual')

    condition: Mapped[str] = mapped_column(String(32), nullable=False, server_default='price_above', index=True)
    threshold: Mapped[float] = mapped_column(Float, nullable=False, server_default='0')
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default='true', index=True)
    one_shot: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default='false')
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default='60')

    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_triggered_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_triggered_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_trigger_source: Mapped[str | None] = mapped_column(String(32), nullable=True)

    last_seen_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_condition_state: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AlertTriggerEvent(Base):
    __tablename__ = 'alert_trigger_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('price_alerts.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    condition: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    trigger_price: Mapped[float] = mapped_column(Float, nullable=False)
    trigger_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
