from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.models.price_alert import PriceAlert
from app.models.watchlist import WatchlistItem
from app.schemas.alerts import PriceAlertCreateRequest, PriceAlertUpdateRequest
from app.services.price_alerts import PriceAlertService
from app.services.realtime_market import SymbolDescriptor


class FakeRealtime:
    def normalize_symbol(self, raw_symbol: str) -> SymbolDescriptor:
        normalized = raw_symbol.strip().upper().replace('/', '')
        if len(normalized) == 6 and normalized.isalpha():
            return SymbolDescriptor(
                canonical=normalized,
                provider_symbol=f'{normalized}=X',
                display_symbol=f'{normalized[:3]}/{normalized[3:]}',
                instrument_type='fx',
            )

        return SymbolDescriptor(
            canonical=normalized,
            provider_symbol=normalized,
            display_symbol=normalized,
            instrument_type='equity',
        )


def build_settings() -> Settings:
    return Settings(
        redis_url='',
        database_url='sqlite+aiosqlite:///:memory:',
        alerts_default_cooldown_seconds=60,
        alerts_trigger_display_seconds=120,
        yahoo_endpoints=['https://query1.finance.yahoo.com/v7/finance/quote'],
    )


@pytest.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_price_alert_crud_and_filtering(db_session: AsyncSession) -> None:
    service = PriceAlertService(settings=build_settings(), realtime_market=FakeRealtime())

    created = await service.create_alert(
        db_session,
        PriceAlertCreateRequest(
            symbol='AAPL',
            condition='price_above',
            threshold=190,
            enabled=True,
            cooldown_seconds=30,
            one_shot=False,
        ),
    )

    assert created.id > 0
    assert created.symbol == 'AAPL'
    assert created.cooldown_seconds == 30

    listed = await service.list_alerts(db_session, symbol='AAPL', status='active')
    assert len(listed) == 1

    patched = await service.update_alert(
        db_session,
        created.id,
        PriceAlertUpdateRequest(enabled=False, threshold=195),
    )
    assert patched.enabled is False
    assert patched.threshold == pytest.approx(195)

    inactive = await service.list_alerts(db_session, symbol='AAPL', status='inactive')
    assert len(inactive) == 1

    removed = await service.delete_alert(db_session, created.id)
    assert removed is True


@pytest.mark.asyncio
async def test_evaluator_honors_crossing_and_cooldown(db_session: AsyncSession) -> None:
    service = PriceAlertService(settings=build_settings(), realtime_market=FakeRealtime())

    alert = await service.create_alert(
        db_session,
        PriceAlertCreateRequest(
            symbol='AAPL',
            condition='crosses_above',
            threshold=100,
            enabled=True,
            cooldown_seconds=60,
            one_shot=False,
        ),
    )

    events = await service.evaluate_snapshot(
        db_session,
        symbol='AAPL',
        last_price=99,
        change_percent=-0.5,
        source='test',
        as_of=datetime.now(timezone.utc),
    )
    assert events == []

    first_trigger = await service.evaluate_snapshot(
        db_session,
        symbol='AAPL',
        last_price=101,
        change_percent=0.8,
        source='test',
        as_of=datetime.now(timezone.utc),
    )
    assert len(first_trigger) == 1

    await service.evaluate_snapshot(
        db_session,
        symbol='AAPL',
        last_price=98,
        change_percent=-1.0,
        source='test',
        as_of=datetime.now(timezone.utc),
    )

    suppressed = await service.evaluate_snapshot(
        db_session,
        symbol='AAPL',
        last_price=101,
        change_percent=0.9,
        source='test',
        as_of=datetime.now(timezone.utc),
    )
    assert suppressed == []

    reloaded = await service.get_alert(db_session, alert.id)
    assert reloaded is not None
    assert reloaded.last_triggered_at is not None

    reloaded.last_triggered_at = datetime.now(timezone.utc) - timedelta(seconds=61)
    await db_session.commit()

    await service.evaluate_snapshot(
        db_session,
        symbol='AAPL',
        last_price=95,
        change_percent=-2.0,
        source='test',
        as_of=datetime.now(timezone.utc),
    )

    second_trigger = await service.evaluate_snapshot(
        db_session,
        symbol='AAPL',
        last_price=105,
        change_percent=1.5,
        source='test',
        as_of=datetime.now(timezone.utc),
    )
    assert len(second_trigger) == 1


@pytest.mark.asyncio
async def test_one_shot_alert_auto_disables_on_trigger(db_session: AsyncSession) -> None:
    service = PriceAlertService(settings=build_settings(), realtime_market=FakeRealtime())

    alert = await service.create_alert(
        db_session,
        PriceAlertCreateRequest(
            symbol='EURUSD',
            condition='percent_move_up',
            threshold=0.5,
            enabled=True,
            one_shot=True,
        ),
    )

    events = await service.evaluate_snapshot(
        db_session,
        symbol='EURUSD',
        last_price=1.09,
        change_percent=0.6,
        source='test',
        as_of=datetime.now(timezone.utc),
    )
    assert len(events) == 1

    reloaded = await service.get_alert(db_session, alert.id)
    assert reloaded is not None
    assert reloaded.enabled is False
