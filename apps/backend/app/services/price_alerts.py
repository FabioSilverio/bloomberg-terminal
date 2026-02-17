from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.price_alert import ALERT_CONDITIONS, AlertTriggerEvent, PriceAlert
from app.models.watchlist import WatchlistItem
from app.schemas.alerts import (
    AlertStatus,
    PriceAlertCreateRequest,
    PriceAlertUpdateRequest,
    PriceAlertUpsertRequest,
)
from app.services.realtime_market import RealtimeMarketService

PRICE_CONDITIONS = {'price_above', 'price_below', 'crosses_above', 'crosses_below'}
PERCENT_CONDITIONS = {'percent_move_up', 'percent_move_down'}


class PriceAlertService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        realtime_market: RealtimeMarketService | None = None,
    ) -> None:
        self.settings = settings
        self.realtime_market = realtime_market

    async def list_alerts(
        self,
        db: AsyncSession,
        *,
        symbol: str | None = None,
        enabled: bool | None = None,
        status: AlertStatus | None = None,
    ) -> list[PriceAlert]:
        query: Select[tuple[PriceAlert]] = select(PriceAlert)

        if symbol:
            canonical = self._normalize_symbol(symbol)
            query = query.where(PriceAlert.symbol == canonical)

        if status == 'active':
            query = query.where(PriceAlert.enabled.is_(True))
        elif status == 'inactive':
            query = query.where(PriceAlert.enabled.is_(False))
        elif enabled is not None:
            query = query.where(PriceAlert.enabled.is_(enabled))

        result = await db.execute(query.order_by(PriceAlert.updated_at.desc(), PriceAlert.id.desc()))
        return list(result.scalars().all())

    async def get_alert(self, db: AsyncSession, alert_id: int) -> PriceAlert | None:
        return await db.get(PriceAlert, alert_id)

    async def list_alerts_for_symbols_map(self, db: AsyncSession, symbols: list[str]) -> dict[str, list[PriceAlert]]:
        canonical_symbols = [self._normalize_symbol(symbol) for symbol in symbols if symbol]
        canonical_symbols = list(dict.fromkeys(canonical_symbols))
        if not canonical_symbols:
            return {}

        result = await db.execute(
            select(PriceAlert).where(PriceAlert.symbol.in_(canonical_symbols)).order_by(PriceAlert.updated_at.desc())
        )

        grouped: dict[str, list[PriceAlert]] = {symbol: [] for symbol in canonical_symbols}
        for alert in result.scalars().all():
            grouped.setdefault(alert.symbol, []).append(alert)
        return grouped

    async def get_alert_map_for_items(self, db: AsyncSession, item_ids: list[int]) -> dict[int, PriceAlert]:
        if not item_ids:
            return {}

        result = await db.execute(
            select(PriceAlert)
            .where(PriceAlert.watchlist_item_id.in_(item_ids))
            .order_by(PriceAlert.updated_at.desc(), PriceAlert.id.desc())
        )
        alerts = list(result.scalars().all())

        mapping: dict[int, PriceAlert] = {}
        for alert in alerts:
            if alert.watchlist_item_id is None:
                continue
            mapping.setdefault(alert.watchlist_item_id, alert)
        return mapping

    async def create_alert(self, db: AsyncSession, payload: PriceAlertCreateRequest) -> PriceAlert:
        symbol, instrument_type, watchlist_item_id, source = await self._resolve_identity(
            db,
            symbol=payload.symbol,
            watchlist_item_id=payload.watchlist_item_id,
            requested_source=payload.source,
        )

        threshold = self._validate_threshold(payload.condition, payload.threshold)
        cooldown_seconds = self._validate_cooldown(payload.cooldown_seconds)
        one_shot = self._resolve_one_shot(payload.one_shot, payload.repeating)

        alert = PriceAlert(
            symbol=symbol,
            instrument_type=instrument_type,
            watchlist_item_id=watchlist_item_id,
            source=source,
            condition=payload.condition,
            threshold=threshold,
            enabled=payload.enabled,
            one_shot=one_shot,
            cooldown_seconds=cooldown_seconds,
            last_condition_state=False,
        )

        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        return alert

    async def update_alert(self, db: AsyncSession, alert_id: int, payload: PriceAlertUpdateRequest) -> PriceAlert:
        alert = await db.get(PriceAlert, alert_id)
        if alert is None:
            raise LookupError('Alert not found')

        fields = payload.model_fields_set

        if {'symbol', 'watchlist_item_id', 'source'} & fields:
            symbol, instrument_type, watchlist_item_id, source = await self._resolve_identity(
                db,
                symbol=payload.symbol if 'symbol' in fields else alert.symbol,
                watchlist_item_id=payload.watchlist_item_id if 'watchlist_item_id' in fields else alert.watchlist_item_id,
                requested_source=payload.source if 'source' in fields else alert.source,
            )
            alert.symbol = symbol
            alert.instrument_type = instrument_type
            alert.watchlist_item_id = watchlist_item_id
            alert.source = source

        condition = payload.condition if payload.condition is not None else alert.condition
        threshold_candidate = payload.threshold if payload.threshold is not None else alert.threshold
        alert.threshold = self._validate_threshold(condition, threshold_candidate)
        alert.condition = condition

        if payload.enabled is not None:
            alert.enabled = payload.enabled

        if payload.cooldown_seconds is not None:
            alert.cooldown_seconds = self._validate_cooldown(payload.cooldown_seconds)

        if payload.one_shot is not None or payload.repeating is not None:
            alert.one_shot = self._resolve_one_shot(payload.one_shot if payload.one_shot is not None else alert.one_shot, payload.repeating)

        await db.commit()
        await db.refresh(alert)
        return alert

    async def delete_alert(self, db: AsyncSession, alert_id: int) -> bool:
        alert = await db.get(PriceAlert, alert_id)
        if alert is None:
            return False

        await db.delete(alert)
        await db.commit()
        return True

    async def upsert_for_watchlist_item(
        self,
        db: AsyncSession,
        item_id: int,
        payload: PriceAlertUpsertRequest,
    ) -> PriceAlert:
        item = await db.get(WatchlistItem, item_id)
        if item is None:
            raise LookupError('Watchlist item not found')

        existing = await db.scalar(
            select(PriceAlert)
            .where(PriceAlert.watchlist_item_id == item_id)
            .order_by(PriceAlert.updated_at.desc(), PriceAlert.id.desc())
        )

        threshold = payload.target_price
        if threshold is None and existing is not None:
            threshold = existing.threshold

        if payload.enabled and threshold is None:
            raise ValueError('targetPrice is required when enabling an alert')

        if threshold is None:
            threshold = 0.0

        threshold = self._validate_threshold('price_above', threshold)
        condition = 'price_above' if payload.direction == 'above' else 'price_below'

        if existing is None:
            existing = PriceAlert(
                watchlist_item_id=item.id,
                symbol=item.symbol,
                instrument_type=item.instrument_type,
                source='watchlist',
                condition=condition,
                threshold=threshold,
                enabled=payload.enabled,
                one_shot=payload.one_shot,
                cooldown_seconds=self._validate_cooldown(payload.cooldown_seconds),
                last_condition_state=False,
            )
            db.add(existing)
        else:
            existing.watchlist_item_id = item.id
            existing.symbol = item.symbol
            existing.instrument_type = item.instrument_type
            existing.source = 'watchlist'
            existing.condition = condition
            existing.threshold = threshold
            existing.enabled = payload.enabled
            existing.one_shot = payload.one_shot
            if payload.cooldown_seconds is not None:
                existing.cooldown_seconds = self._validate_cooldown(payload.cooldown_seconds)

        await db.commit()
        await db.refresh(existing)
        return existing

    async def delete_for_watchlist_item(self, db: AsyncSession, item_id: int) -> bool:
        alert = await db.scalar(
            select(PriceAlert)
            .where(PriceAlert.watchlist_item_id == item_id)
            .order_by(PriceAlert.updated_at.desc(), PriceAlert.id.desc())
        )
        if alert is None:
            return False

        await db.delete(alert)
        await db.commit()
        return True

    async def list_events(
        self,
        db: AsyncSession,
        *,
        symbol: str | None = None,
        alert_id: int | None = None,
        after_id: int | None = None,
        limit: int = 50,
    ) -> list[AlertTriggerEvent]:
        bounded_limit = max(1, min(limit, 200))
        query: Select[tuple[AlertTriggerEvent]] = select(AlertTriggerEvent)

        if symbol:
            query = query.where(AlertTriggerEvent.symbol == self._normalize_symbol(symbol))

        if alert_id is not None:
            query = query.where(AlertTriggerEvent.alert_id == alert_id)

        if after_id is not None:
            query = query.where(AlertTriggerEvent.id > after_id).order_by(AlertTriggerEvent.id.asc())
        else:
            query = query.order_by(AlertTriggerEvent.id.desc())

        result = await db.execute(query.limit(bounded_limit))
        return list(result.scalars().all())

    async def evaluate_snapshot(
        self,
        db: AsyncSession,
        *,
        symbol: str,
        last_price: float,
        change_percent: float,
        source: str,
        as_of: datetime | None = None,
    ) -> list[AlertTriggerEvent]:
        if not isinstance(last_price, (int, float)) or last_price <= 0:
            return []

        canonical = self._normalize_symbol(symbol)
        timestamp = as_of.astimezone(timezone.utc) if as_of else datetime.now(timezone.utc)

        result = await db.execute(
            select(PriceAlert)
            .where(PriceAlert.symbol == canonical)
            .where(PriceAlert.enabled.is_(True))
            .order_by(PriceAlert.id.asc())
        )
        alerts = list(result.scalars().all())
        if not alerts:
            return []

        triggered_events: list[AlertTriggerEvent] = []
        dirty = False

        for alert in alerts:
            condition_met, transition_triggered = self._evaluate_condition(alert, last_price=last_price, change_percent=change_percent)
            previous_condition_state = bool(alert.last_condition_state)
            should_trigger = transition_triggered

            if alert.condition in {'price_above', 'price_below', 'percent_move_up', 'percent_move_down'}:
                should_trigger = condition_met and not previous_condition_state

            if should_trigger and self._is_within_cooldown(alert, timestamp):
                should_trigger = False

            if alert.last_condition_state != condition_met:
                alert.last_condition_state = condition_met
                dirty = True

            if alert.last_seen_price != float(last_price):
                alert.last_seen_price = float(last_price)
                dirty = True

            if should_trigger:
                event = AlertTriggerEvent(
                    alert_id=alert.id,
                    symbol=alert.symbol,
                    condition=alert.condition,
                    threshold=alert.threshold,
                    trigger_price=float(last_price),
                    trigger_value=float(change_percent),
                    source=source,
                    triggered_at=timestamp,
                )
                db.add(event)
                triggered_events.append(event)

                alert.last_triggered_at = timestamp
                alert.last_triggered_price = float(last_price)
                alert.last_triggered_value = float(change_percent)
                alert.last_trigger_source = source

                if alert.one_shot:
                    alert.enabled = False

                dirty = True

        if not dirty:
            return []

        await db.commit()

        for event in triggered_events:
            await db.refresh(event)

        return triggered_events

    def compute_trigger_state(self, alert: PriceAlert, now: datetime | None = None) -> tuple[str, bool, bool]:
        timestamp = now or datetime.now(timezone.utc)
        in_cooldown = self._is_within_cooldown(alert, timestamp)

        if not alert.enabled:
            return 'inactive', False, False

        trigger_display_seconds = max(5, int(getattr(self.settings, 'alerts_trigger_display_seconds', 120)))
        recently_triggered = (
            alert.last_triggered_at is not None
            and (timestamp - alert.last_triggered_at).total_seconds() <= trigger_display_seconds
        )

        if recently_triggered:
            return 'triggered', bool(alert.last_condition_state), in_cooldown

        if in_cooldown:
            return 'cooldown', bool(alert.last_condition_state), True

        if alert.last_condition_state:
            return 'active', True, False

        return 'armed', False, False

    async def _resolve_identity(
        self,
        db: AsyncSession,
        *,
        symbol: str | None,
        watchlist_item_id: int | None,
        requested_source: str | None,
    ) -> tuple[str, str | None, int | None, str]:
        item: WatchlistItem | None = None
        if watchlist_item_id is not None:
            item = await db.get(WatchlistItem, watchlist_item_id)
            if item is None:
                raise LookupError('Watchlist item not found')

        if item is not None:
            canonical = item.symbol
            instrument_type = item.instrument_type
            resolved_watchlist_id = item.id
        else:
            if not symbol:
                raise ValueError('symbol is required when watchlistItemId is not provided')
            canonical = self._normalize_symbol(symbol)
            instrument_type = self._infer_instrument_type(symbol)
            resolved_watchlist_id = None

        source = requested_source or ('watchlist' if item is not None else 'manual')

        return canonical, instrument_type, resolved_watchlist_id, source

    def _infer_instrument_type(self, symbol: str) -> str | None:
        if self.realtime_market is None:
            return None
        try:
            descriptor = self.realtime_market.normalize_symbol(symbol)
            return descriptor.instrument_type
        except Exception:
            return None

    def _normalize_symbol(self, raw_symbol: str) -> str:
        candidate = (raw_symbol or '').strip().upper()
        if not candidate:
            raise ValueError('Symbol is required')

        if self.realtime_market is None:
            return candidate

        try:
            descriptor = self.realtime_market.normalize_symbol(candidate)
            return descriptor.canonical
        except Exception:
            return candidate

    @staticmethod
    def _resolve_one_shot(one_shot: bool, repeating: bool | None) -> bool:
        if repeating is None:
            return bool(one_shot)
        return not repeating

    def _validate_threshold(self, condition: str, threshold: float) -> float:
        if condition not in ALERT_CONDITIONS:
            raise ValueError(f'Unsupported alert condition: {condition}')

        if threshold is None:
            raise ValueError('threshold is required')

        try:
            threshold_value = float(threshold)
        except (TypeError, ValueError) as exc:
            raise ValueError('threshold must be numeric') from exc

        if threshold_value <= 0:
            raise ValueError('threshold must be greater than zero')

        if condition in PERCENT_CONDITIONS and threshold_value > 100:
            raise ValueError('percentage threshold must be <= 100')

        return threshold_value

    def _validate_cooldown(self, cooldown_seconds: int | None) -> int:
        default_cooldown = int(getattr(self.settings, 'alerts_default_cooldown_seconds', 60))
        value = default_cooldown if cooldown_seconds is None else int(cooldown_seconds)
        if value < 0:
            raise ValueError('cooldownSeconds must be >= 0')
        if value > 24 * 60 * 60:
            raise ValueError('cooldownSeconds is too large (max 86400)')
        return value

    @staticmethod
    def _is_within_cooldown(alert: PriceAlert, now: datetime) -> bool:
        if alert.last_triggered_at is None:
            return False
        cooldown = max(0, int(alert.cooldown_seconds or 0))
        if cooldown == 0:
            return False
        return (now - alert.last_triggered_at).total_seconds() < cooldown

    @staticmethod
    def _evaluate_condition(alert: PriceAlert, *, last_price: float, change_percent: float) -> tuple[bool, bool]:
        threshold = float(alert.threshold)
        previous_price = alert.last_seen_price

        if alert.condition == 'price_above':
            condition_met = last_price >= threshold
            return condition_met, condition_met and not bool(alert.last_condition_state)

        if alert.condition == 'price_below':
            condition_met = last_price <= threshold
            return condition_met, condition_met and not bool(alert.last_condition_state)

        if alert.condition == 'crosses_above':
            condition_met = last_price > threshold
            crossed = previous_price is not None and previous_price <= threshold < last_price
            return condition_met, crossed

        if alert.condition == 'crosses_below':
            condition_met = last_price < threshold
            crossed = previous_price is not None and previous_price >= threshold > last_price
            return condition_met, crossed

        if alert.condition == 'percent_move_up':
            condition_met = change_percent >= threshold
            return condition_met, condition_met and not bool(alert.last_condition_state)

        if alert.condition == 'percent_move_down':
            condition_met = change_percent <= -abs(threshold)
            return condition_met, condition_met and not bool(alert.last_condition_state)

        return False, False
