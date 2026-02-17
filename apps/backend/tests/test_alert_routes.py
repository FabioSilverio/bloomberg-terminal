from __future__ import annotations

import os
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')

from app.api.routes import alerts as alert_routes


class FakeAlertService:
    def __init__(self) -> None:
        self.store: dict[int, SimpleNamespace] = {}

    async def list_alerts(self, _db):
        return list(self.store.values())

    async def upsert_for_watchlist_item(self, _db, item_id: int, payload):
        if payload.enabled and payload.target_price is None:
            raise ValueError('targetPrice is required when enabling an alert')

        now = datetime.now(timezone.utc)
        current = self.store.get(item_id)
        target_price = payload.target_price if payload.target_price is not None else (current.target_price if current else None)
        alert = SimpleNamespace(
            id=(current.id if current else item_id + 200),
            watchlist_item_id=item_id,
            symbol='AAPL',
            enabled=payload.enabled,
            direction=payload.direction,
            target_price=target_price,
            created_at=current.created_at if current else now,
            updated_at=now,
        )
        self.store[item_id] = alert
        return alert

    async def delete_for_watchlist_item(self, _db, item_id: int) -> bool:
        return self.store.pop(item_id, None) is not None


async def override_db():
    yield object()


@pytest.mark.asyncio
async def test_alert_routes_upsert_and_list(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeAlertService()
    container = type('Container', (), {'price_alerts': service})()

    monkeypatch.setattr(alert_routes, 'get_container', lambda: container)

    app = FastAPI()
    app.include_router(alert_routes.router, prefix='/api/v1')
    app.dependency_overrides[alert_routes.get_db] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        created = await client.put(
            '/api/v1/alerts/watchlist/1',
            json={'enabled': True, 'direction': 'above', 'targetPrice': 123.4},
        )
        listed = await client.get('/api/v1/alerts')

    assert created.status_code == 200
    assert created.json()['targetPrice'] == pytest.approx(123.4)

    assert listed.status_code == 200
    assert listed.json()['items']
    assert listed.json()['items'][0]['watchlistItemId'] == 1


@pytest.mark.asyncio
async def test_alert_routes_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeAlertService()
    container = type('Container', (), {'price_alerts': service})()

    monkeypatch.setattr(alert_routes, 'get_container', lambda: container)

    app = FastAPI()
    app.include_router(alert_routes.router, prefix='/api/v1')
    app.dependency_overrides[alert_routes.get_db] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.put('/api/v1/alerts/watchlist/1', json={'enabled': True, 'direction': 'above'})

    assert response.status_code == 400
    assert 'targetPrice' in response.json()['detail']
