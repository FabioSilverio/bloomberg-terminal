from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import pytest

from app.core.config import Settings
from app.services.realtime_market import RealtimeMarketService


class FakeCache:
    def __init__(self) -> None:
        self.store: dict[str, tuple[Any, float]] = {}

    async def get(self, key: str) -> Any | None:
        item = self.store.get(key)
        if item is None:
            return None

        payload, expires_at = item
        if expires_at < time.time():
            self.store.pop(key, None)
            return None
        return payload

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self.store[key] = (value, time.time() + max(ttl_seconds, 0))


class FakeHttp:
    def __init__(self) -> None:
        self.yahoo_calls = 0
        self.fail_yahoo = False
        self.fail_stooq = False
        self.latency_seconds = 0.0

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        if 'finance.yahoo.com/v8/finance/chart' not in url:
            raise RuntimeError(f'unexpected url: {url}')

        self.yahoo_calls += 1
        if self.fail_yahoo:
            raise RuntimeError('yahoo down')

        if self.latency_seconds > 0:
            await asyncio.sleep(self.latency_seconds)

        now = int(datetime.now(timezone.utc).timestamp())
        return {
            'chart': {
                'result': [
                    {
                        'meta': {
                            'currency': 'USD',
                            'regularMarketPrice': 101.5,
                            'chartPreviousClose': 100.0,
                            'regularMarketTime': now,
                            'regularMarketVolume': 1_250_000,
                        },
                        'timestamp': [now - 600, now - 300, now],
                        'indicators': {
                            'quote': [
                                {
                                    'close': [100.3, 100.9, 101.5],
                                    'volume': [1000, 1200, 1500],
                                }
                            ]
                        },
                    }
                ],
                'error': None,
            }
        }

    async def get_text(self, url: str, **kwargs: Any) -> str:
        if 'stooq.com' not in url:
            raise RuntimeError(f'unexpected url: {url}')
        if self.fail_stooq:
            raise RuntimeError('stooq down')

        return 'AAPL.US,2026-02-17,12:00:00,100.0,102.0,99.0,101.0,1450000,Apple Inc\n'


def build_settings(**overrides: Any) -> Settings:
    defaults = {
        'redis_url': '',
        'market_cache_ttl_seconds': 2,
        'market_upstream_refresh_seconds': 120,
        'market_stale_ttl_seconds': 300,
        'yahoo_endpoints': ['https://query1.finance.yahoo.com/v7/finance/quote'],
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.asyncio
async def test_normalize_symbol_supports_equity_fx_and_aliases() -> None:
    service = RealtimeMarketService(build_settings(), FakeCache(), FakeHttp())

    eq = service.normalize_symbol('AAPL')
    fx = service.normalize_symbol('eur/usd')
    fx_alt = service.normalize_symbol('EURUSD')

    assert eq.provider_symbol == 'AAPL'
    assert eq.instrument_type == 'equity'

    assert fx.provider_symbol == 'EURUSD=X'
    assert fx.display_symbol == 'EUR/USD'
    assert fx.instrument_type == 'fx'

    assert fx_alt.provider_symbol == 'EURUSD=X'


@pytest.mark.asyncio
async def test_intraday_uses_ui_cache_to_avoid_extra_provider_calls() -> None:
    http = FakeHttp()
    service = RealtimeMarketService(build_settings(), FakeCache(), http)

    first = await service.get_intraday('AAPL')
    second = await service.get_intraday('AAPL')

    assert first.last_price > 0
    assert second.last_price == first.last_price
    assert http.yahoo_calls == 1


@pytest.mark.asyncio
async def test_intraday_coalesces_parallel_requests() -> None:
    cache = FakeCache()
    http = FakeHttp()
    http.latency_seconds = 0.05

    service = RealtimeMarketService(build_settings(), cache, http)

    payloads = await asyncio.gather(*(service.get_intraday('AAPL') for _ in range(6)))

    assert len(payloads) == 6
    assert all(item.last_price > 0 for item in payloads)
    assert http.yahoo_calls == 1


@pytest.mark.asyncio
async def test_intraday_falls_back_to_stale_upstream_snapshot_when_live_fails() -> None:
    cache = FakeCache()
    http = FakeHttp()
    service = RealtimeMarketService(
        build_settings(
            market_cache_ttl_seconds=0,
            market_upstream_refresh_seconds=0,
        ),
        cache,
        http,
    )

    baseline = await service.get_intraday('AAPL')
    assert baseline.last_price > 0

    http.fail_yahoo = True
    http.fail_stooq = True

    # Force bypass of immediate UI cache so upstream fallback path is exercised.
    cache.store.pop('market:intraday:AAPL:ui', None)

    stale = await service.get_intraday('AAPL')

    assert stale.last_price == baseline.last_price
    assert stale.stale is True
    assert any('stale snapshot' in warning.lower() for warning in stale.warnings)
