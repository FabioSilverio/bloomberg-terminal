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
        self.next_id = 200
        self.events = [
            SimpleNamespace(
                id=1,
                alert_id=777,
                symbol='AAPL',
                condition='price_above',
                threshold=200.0,
                trigger_price=201.5,
                trigger_value=2.4,
                source='watchlist:Yahoo',
                triggered_at=datetime.now(timezone.utc),
            )
        ]

    async def list_alerts(self, _db, *, symbol=None, enabled=None, status=None):
        items = list(self.store.values())
        if symbol:
            items = [item for item in items if item.symbol == symbol]
        if status == 'active':
            items = [item for item in items if item.enabled]
        if status == 'inactive':
            items = [item for item in items if not item.enabled]
        if enabled is not None:
            items = [item for item in items if item.enabled is enabled]
        return items

    async def create_alert(self, _db, payload):
        if payload.threshold <= 0:
            raise ValueError('threshold must be greater than zero')

        self.next_id += 1
        now = datetime.now(timezone.utc)
        alert = SimpleNamespace(
            id=self.next_id,
            watchlist_item_id=payload.watchlist_item_id,
            symbol=(payload.symbol or 'AAPL').upper(),
            instrument_type='equity',
            source=payload.source or 'manual',
            condition=payload.condition,
            threshold=payload.threshold,
            enabled=payload.enabled,
            one_shot=payload.one_shot,
            cooldown_seconds=payload.cooldown_seconds or 60,
            last_condition_state=False,
            last_triggered_at=None,
            last_triggered_price=None,
            last_triggered_value=None,
            last_trigger_source=None,
            created_at=now,
            updated_at=now,
        )
        self.store[alert.id] = alert
        return alert

    async def get_alert(self, _db, alert_id: int):
        return self.store.get(alert_id)

    async def update_alert(self, _db, alert_id: int, payload):
        alert = self.store.get(alert_id)
        if alert is None:
            raise LookupError('Alert not found')

        if payload.enabled is not None:
            alert.enabled = payload.enabled
        if payload.threshold is not None:
            if payload.threshold <= 0:
                raise ValueError('threshold must be greater than zero')
            alert.threshold = payload.threshold

        alert.updated_at = datetime.now(timezone.utc)
        return alert

    async def delete_alert(self, _db, alert_id: int) -> bool:
        return self.store.pop(alert_id, None) is not None

    async def list_events(self, _db, **_kwargs):
        return self.events

    async def upsert_for_watchlist_item(self, _db, item_id: int, payload):
        now = datetime.now(timezone.utc)
        alert = SimpleNamespace(
            id=item_id + 50,
            watchlist_item_id=item_id,
            symbol='AAPL',
            instrument_type='equity',
            source='watchlist',
            condition='price_above' if payload.direction == 'above' else 'price_below',
            threshold=payload.target_price or 100,
            enabled=payload.enabled,
            one_shot=payload.one_shot,
            cooldown_seconds=payload.cooldown_seconds or 60,
            last_condition_state=False,
            last_triggered_at=None,
            last_triggered_price=None,
            last_triggered_value=None,
            last_trigger_source=None,
            created_at=now,
            updated_at=now,
        )
        self.store[alert.id] = alert
        return alert

    async def delete_for_watchlist_item(self, _db, item_id: int) -> bool:
        for key, value in list(self.store.items()):
            if value.watchlist_item_id == item_id:
                self.store.pop(key)
                return True
        return False

    def compute_trigger_state(self, _alert, now):
        return 'armed', False, False


async def override_db():
    yield object()


@pytest.mark.asyncio
async def test_alert_routes_crud_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeAlertService()
    container = type('Container', (), {'price_alerts': service})()

    monkeypatch.setattr(alert_routes, 'get_container', lambda: container)

    app = FastAPI()
    app.include_router(alert_routes.router, prefix='/api/v1')
    app.dependency_overrides[alert_routes.get_db] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        created = await client.post(
            '/api/v1/alerts',
            json={
                'symbol': 'AAPL',
                'condition': 'price_above',
                'threshold': 200,
                'enabled': True,
                'oneShot': False,
                'cooldownSeconds': 30,
            },
        )
        created_id = created.json()['id']

        listed = await client.get('/api/v1/alerts', params={'symbol': 'AAPL', 'status': 'active'})
        patched = await client.patch(f'/api/v1/alerts/{created_id}', json={'enabled': False})
        deleted = await client.delete(f'/api/v1/alerts/{created_id}')

    assert created.status_code == 201
    assert created.json()['threshold'] == pytest.approx(200)
    assert listed.status_code == 200
    assert len(listed.json()['items']) == 1
    assert patched.status_code == 200
    assert patched.json()['enabled'] is False
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_alert_routes_event_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeAlertService()
    container = type('Container', (), {'price_alerts': service})()

    monkeypatch.setattr(alert_routes, 'get_container', lambda: container)

    app = FastAPI()
    app.include_router(alert_routes.router, prefix='/api/v1')
    app.dependency_overrides[alert_routes.get_db] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/v1/alerts/events', params={'afterId': 0, 'limit': 10})

    assert response.status_code == 200
    body = response.json()
    assert body['items']
    assert body['items'][0]['symbol'] == 'AAPL'
    assert body['items'][0]['alertId'] == 777
