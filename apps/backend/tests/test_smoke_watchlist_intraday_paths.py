from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import market as market_routes
from app.api.routes import watchlist as watchlist_routes
from app.schemas.intraday import IntradayPoint, IntradayResponse


class FakeWatchlistService:
    def __init__(self) -> None:
        self.items: list[SimpleNamespace] = []
        self.next_id = 1

    async def get_snapshot(self, _db):
        return {
            'asOf': datetime.now(timezone.utc).isoformat(),
            'items': [
                {
                    'id': item.id,
                    'symbol': item.symbol,
                    'displaySymbol': item.display_symbol,
                    'instrumentType': item.instrument_type,
                    'position': item.position,
                    'createdAt': item.created_at.isoformat(),
                    'quote': None,
                    'alerts': [],
                }
                for item in self.items
            ],
            'warnings': [],
        }

    async def add_symbol(self, _db, raw_symbol: str):
        normalized = raw_symbol.upper().replace('/', '').replace('-', '')
        if normalized == 'USDBRL':
            symbol = 'USDBRL'
            display = 'USD/BRL'
            instrument_type = 'fx'
        else:
            symbol = raw_symbol.upper()
            display = symbol
            instrument_type = 'equity'

        item = SimpleNamespace(
            id=self.next_id,
            symbol=symbol,
            display_symbol=display,
            instrument_type=instrument_type,
            position=self.next_id,
            created_at=datetime.now(timezone.utc),
        )
        self.next_id += 1
        self.items.append(item)
        return item, True

    async def remove_item(self, _db, item_id: int):
        before = len(self.items)
        self.items = [item for item in self.items if item.id != item_id]
        return len(self.items) < before

    async def remove_symbol(self, _db, raw_symbol: str):
        before = len(self.items)
        token = raw_symbol.upper().replace('/', '').replace('-', '')
        self.items = [item for item in self.items if item.symbol.replace('/', '').replace('-', '') != token]
        return len(self.items) < before

    async def reorder(self, _db, _ordered_item_ids: list[int]):
        return self.items


class FakeRealtimeMarket:
    async def get_intraday(self, raw_symbol: str):
        symbol = raw_symbol.upper().replace('/', '')
        if symbol == 'BRLUSD':
            symbol = 'USDBRL'
        display_symbol = f'{symbol[:3]}/{symbol[3:]}' if len(symbol) == 6 else symbol

        return IntradayResponse(
            symbol=symbol,
            display_symbol=display_symbol,
            instrument_type='fx' if len(symbol) == 6 else 'equity',
            source='smoke-test',
            as_of=datetime.now(timezone.utc),
            last_price=5.1,
            change=0.02,
            change_percent=0.4,
            volume=1234,
            currency='BRL' if symbol == 'USDBRL' else 'USD',
            stale=False,
            warnings=[],
            points=[IntradayPoint(time=datetime.now(timezone.utc), price=5.1, volume=1234)],
        )


class FakeAlertService:
    async def evaluate_snapshot(self, *_args, **_kwargs):
        return []


async def override_db():
    yield object()


@pytest.mark.asyncio
async def test_watchlist_add_and_intraday_smoke_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    container = type(
        'Container',
        (),
        {
            'watchlist': FakeWatchlistService(),
            'realtime_market': FakeRealtimeMarket(),
            'price_alerts': FakeAlertService(),
            'settings': type('Settings', (), {'market_ws_interval_seconds': 2})(),
        },
    )()

    monkeypatch.setattr(watchlist_routes, 'get_container', lambda: container)
    monkeypatch.setattr(market_routes, 'get_container', lambda: container)

    app = FastAPI()
    app.include_router(watchlist_routes.router, prefix='/api/v1')
    app.include_router(market_routes.router, prefix='/api/v1')
    app.dependency_overrides[watchlist_routes.get_db] = override_db
    app.dependency_overrides[market_routes.get_db] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        added = await client.post('/api/v1/watchlist', json={'symbol': 'USD/BRL'})
        watchlist = await client.get('/api/v1/watchlist')
        intraday = await client.get('/api/v1/market/intraday/BRLUSD')

    assert added.status_code == 201
    assert added.json()['symbol'] == 'USDBRL'
    assert watchlist.status_code == 200
    assert watchlist.json()['items']
    assert watchlist.json()['items'][0]['displaySymbol'] == 'USD/BRL'
    assert intraday.status_code == 200
    assert intraday.json()['symbol'] == 'USDBRL'
    assert intraday.json()['displaySymbol'] == 'USD/BRL'
