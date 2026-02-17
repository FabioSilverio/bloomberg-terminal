from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.schemas.intraday import IntradayResponse
from app.services.realtime_market import SymbolDescriptor
from app.services.watchlist import WatchlistService


class FakeRealtime:
    def normalize_symbol(self, raw_symbol: str) -> SymbolDescriptor:
        symbol = raw_symbol.strip().upper()
        if len(symbol) == 6 and symbol.isalpha():
            return SymbolDescriptor(
                canonical=symbol,
                provider_symbol=f'{symbol}=X',
                display_symbol=f'{symbol[:3]}/{symbol[3:]}',
                instrument_type='fx',
            )

        return SymbolDescriptor(
            canonical=symbol,
            provider_symbol=symbol,
            display_symbol=symbol,
            instrument_type='equity',
        )

    async def get_intraday(self, symbol: str) -> IntradayResponse:
        return IntradayResponse(
            symbol=symbol,
            display_symbol=symbol,
            instrument_type='equity',
            source='test-feed',
            as_of=datetime.now(timezone.utc),
            last_price=123.45,
            change=1.2,
            change_percent=0.98,
            volume=1000,
            currency='USD',
            stale=False,
            warnings=[],
            points=[],
        )


class FakeAlertService:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.evaluated_symbols: list[str] = []

    async def evaluate_snapshot(self, _db, *, symbol: str, **_kwargs):
        self.evaluated_symbols.append(symbol)
        return []

    async def list_alerts_for_symbols_map(self, _db, symbols: list[str]):
        if not self.enabled:
            return {}

        now = datetime.now(timezone.utc)
        payload = {}
        for index, symbol in enumerate(symbols, start=1):
            payload[symbol] = [
                SimpleNamespace(
                    id=100 + index,
                    enabled=True,
                    source='watchlist',
                    condition='price_above',
                    threshold=130.0,
                    one_shot=False,
                    cooldown_seconds=60,
                    last_triggered_at=now,
                    last_trigger_source='watchlist:test-feed',
                    updated_at=now,
                    last_condition_state=True,
                )
            ]
        return payload

    def compute_trigger_state(self, _alert, now):
        return 'triggered', True, False


class FakeDb:
    def __init__(self, scalar_values: list[object | None]) -> None:
        self._scalar_values = list(scalar_values)
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.refreshed: list[object] = []

    async def scalar(self, _query):
        return self._scalar_values.pop(0) if self._scalar_values else None

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        return None

    async def refresh(self, value):
        value.id = 1
        self.refreshed.append(value)

    async def get(self, _model, _id):
        return None

    async def delete(self, value):
        self.deleted.append(value)


def build_settings() -> Settings:
    return Settings(
        redis_url='',
        watchlist_max_items=10,
        yahoo_endpoints=['https://query1.finance.yahoo.com/v7/finance/quote'],
    )


@pytest.mark.asyncio
async def test_add_symbol_creates_watchlist_item_with_position() -> None:
    service = WatchlistService(settings=build_settings(), realtime_market=FakeRealtime())
    db = FakeDb([None, 0, None])

    item, created = await service.add_symbol(db, 'AAPL')

    assert created is True
    assert item.symbol == 'AAPL'
    assert item.position == 1
    assert db.added
    assert db.refreshed


@pytest.mark.asyncio
async def test_get_snapshot_maps_quotes_for_each_item(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_alerts = FakeAlertService()
    service = WatchlistService(
        settings=build_settings(),
        realtime_market=FakeRealtime(),
        price_alerts=fake_alerts,
    )

    items = [
        SimpleNamespace(
            id=1,
            symbol='AAPL',
            display_symbol='AAPL',
            instrument_type='equity',
            position=1,
            created_at=datetime.now(timezone.utc),
        ),
        SimpleNamespace(
            id=2,
            symbol='EURUSD',
            display_symbol='EUR/USD',
            instrument_type='fx',
            position=2,
            created_at=datetime.now(timezone.utc),
        ),
    ]

    async def fake_list_items(_db):
        return items

    monkeypatch.setattr(service, '_list_items', fake_list_items)

    snapshot = await service.get_snapshot(db=object())

    assert len(snapshot.items) == 2
    assert snapshot.items[0].quote is not None
    assert snapshot.items[0].quote.source == 'test-feed'
    assert snapshot.items[1].display_symbol == 'EUR/USD'
    assert snapshot.items[0].alerts
    assert snapshot.items[0].alerts[0].threshold == pytest.approx(130.0)
    assert set(fake_alerts.evaluated_symbols) == {'AAPL', 'EURUSD'}
