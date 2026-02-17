from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.watchlist import WatchlistItem
from app.schemas.watchlist import WatchlistItemResponse, WatchlistQuote, WatchlistResponse
from app.services.realtime_market import RealtimeMarketService


class WatchlistService:
    def __init__(self, settings: Settings, realtime_market: RealtimeMarketService) -> None:
        self.settings = settings
        self.realtime_market = realtime_market

    async def get_snapshot(self, db: AsyncSession) -> WatchlistResponse:
        items = await self._list_items(db)
        warnings: list[str] = []

        if not items:
            return WatchlistResponse(as_of=datetime.now(timezone.utc), items=[], warnings=[])

        quote_results = await asyncio.gather(
            *(self.realtime_market.get_intraday(item.symbol) for item in items),
            return_exceptions=True,
        )

        payload_items: list[WatchlistItemResponse] = []
        for item, result in zip(items, quote_results):
            quote_payload: WatchlistQuote | None = None

            if isinstance(result, Exception):
                warnings.append(f'{item.display_symbol}: {self._summarize_error(result)}')
            else:
                quote_payload = WatchlistQuote(
                    source=result.source,
                    as_of=result.as_of,
                    last_price=result.last_price,
                    change=result.change,
                    change_percent=result.change_percent,
                    volume=result.volume,
                    currency=result.currency,
                    stale=result.stale,
                    freshness_seconds=result.freshness_seconds,
                )
                warnings.extend(result.warnings)

            payload_items.append(
                WatchlistItemResponse(
                    id=item.id,
                    symbol=item.symbol,
                    display_symbol=item.display_symbol,
                    instrument_type=item.instrument_type,
                    position=item.position,
                    created_at=item.created_at,
                    quote=quote_payload,
                )
            )

        return WatchlistResponse(
            as_of=datetime.now(timezone.utc),
            items=payload_items,
            warnings=self._dedupe(warnings),
        )

    async def add_symbol(self, db: AsyncSession, raw_symbol: str) -> tuple[WatchlistItem, bool]:
        descriptor = self.realtime_market.normalize_symbol(raw_symbol)

        existing = await db.scalar(select(WatchlistItem).where(WatchlistItem.symbol == descriptor.canonical))
        if existing is not None:
            return existing, False

        total_items = await db.scalar(select(func.count(WatchlistItem.id))) or 0
        if total_items >= self.settings.watchlist_max_items:
            raise ValueError(f'Watchlist limit reached ({self.settings.watchlist_max_items})')

        max_position = await db.scalar(select(func.max(WatchlistItem.position)))
        next_position = int(max_position or 0) + 1

        item = WatchlistItem(
            symbol=descriptor.canonical,
            display_symbol=descriptor.display_symbol,
            provider_symbol=descriptor.provider_symbol,
            instrument_type=descriptor.instrument_type,
            position=next_position,
        )

        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item, True

    async def remove_item(self, db: AsyncSession, item_id: int) -> bool:
        item = await db.get(WatchlistItem, item_id)
        if item is None:
            return False

        await db.delete(item)
        await db.commit()
        await self._compact_positions(db)
        return True

    async def remove_symbol(self, db: AsyncSession, raw_symbol: str) -> bool:
        descriptor = self.realtime_market.normalize_symbol(raw_symbol)
        item = await db.scalar(select(WatchlistItem).where(WatchlistItem.symbol == descriptor.canonical))
        if item is None:
            return False

        await db.delete(item)
        await db.commit()
        await self._compact_positions(db)
        return True

    async def reorder(self, db: AsyncSession, ordered_item_ids: list[int]) -> list[WatchlistItem]:
        items = await self._list_items(db)
        if not items:
            return []

        by_id = {item.id: item for item in items}
        used: set[int] = set()

        next_position = 1
        for item_id in ordered_item_ids:
            item = by_id.get(item_id)
            if item is None:
                continue
            item.position = next_position
            used.add(item_id)
            next_position += 1

        for item in items:
            if item.id in used:
                continue
            item.position = next_position
            next_position += 1

        await db.commit()
        return await self._list_items(db)

    async def _list_items(self, db: AsyncSession) -> list[WatchlistItem]:
        result = await db.execute(select(WatchlistItem).order_by(WatchlistItem.position.asc(), WatchlistItem.id.asc()))
        return list(result.scalars().all())

    async def _compact_positions(self, db: AsyncSession) -> None:
        items = await self._list_items(db)
        for idx, item in enumerate(items, start=1):
            item.position = idx
        await db.commit()

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for item in items:
            if item in seen:
                continue
            output.append(item)
            seen.add(item)
        return output

    @staticmethod
    def _summarize_error(exc: Exception) -> str:
        message = str(exc).strip()
        return message[:180] if message else exc.__class__.__name__
