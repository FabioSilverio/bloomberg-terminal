from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_alert import PriceAlert
from app.models.watchlist import WatchlistItem
from app.schemas.alerts import PriceAlertUpsertRequest


class PriceAlertService:
    async def list_alerts(self, db: AsyncSession) -> list[PriceAlert]:
        result = await db.execute(select(PriceAlert).order_by(PriceAlert.updated_at.desc(), PriceAlert.id.desc()))
        return list(result.scalars().all())

    async def get_alert_map_for_items(self, db: AsyncSession, item_ids: list[int]) -> dict[int, PriceAlert]:
        if not item_ids:
            return {}

        result = await db.execute(select(PriceAlert).where(PriceAlert.watchlist_item_id.in_(item_ids)))
        alerts = list(result.scalars().all())
        return {alert.watchlist_item_id: alert for alert in alerts}

    async def upsert_for_watchlist_item(
        self,
        db: AsyncSession,
        item_id: int,
        payload: PriceAlertUpsertRequest,
    ) -> PriceAlert:
        item = await db.get(WatchlistItem, item_id)
        if item is None:
            raise LookupError('Watchlist item not found')

        existing = await db.scalar(select(PriceAlert).where(PriceAlert.watchlist_item_id == item_id))
        target_price = payload.target_price if payload.target_price is not None else (existing.target_price if existing else None)

        if target_price is not None and target_price <= 0:
            raise ValueError('targetPrice must be greater than zero')

        if payload.enabled and target_price is None:
            raise ValueError('targetPrice is required when enabling an alert')

        if existing is None:
            alert = PriceAlert(
                watchlist_item_id=item_id,
                symbol=item.symbol,
                enabled=payload.enabled,
                direction=payload.direction,
                target_price=target_price,
            )
            db.add(alert)
        else:
            alert = existing
            alert.symbol = item.symbol
            alert.enabled = payload.enabled
            alert.direction = payload.direction
            alert.target_price = target_price

        await db.commit()
        await db.refresh(alert)
        return alert

    async def delete_for_watchlist_item(self, db: AsyncSession, item_id: int) -> bool:
        alert = await db.scalar(select(PriceAlert).where(PriceAlert.watchlist_item_id == item_id))
        if alert is None:
            return False

        await db.delete(alert)
        await db.commit()
        return True
