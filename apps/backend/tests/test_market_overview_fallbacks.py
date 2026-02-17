from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import market as market_routes
from app.core.config import Settings
from app.schemas.market import MarketOverviewResponse, MarketPoint, MarketSections
from app.services.market_overview import MarketOverviewService


class FakeCache:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        return self.store.get(key)

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self.store[key] = value


class FakeHttp:
    def __init__(self, *, fail_all: bool = False) -> None:
        self.fail_all = fail_all

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        if self.fail_all:
            raise RuntimeError('provider unavailable')

        if 'finance.yahoo.com' in url:
            raise RuntimeError('HTTP 429')

        if 'coingecko' in url:
            return {
                'bitcoin': {'usd': 64000.0, 'usd_24h_change': 1.2},
                'ethereum': {'usd': 3200.0, 'usd_24h_change': -0.8},
                'solana': {'usd': 120.0, 'usd_24h_change': 2.5},
            }

        raise RuntimeError(f'unexpected get_json url: {url}')

    async def get_text(self, url: str, **kwargs: Any) -> str:
        if self.fail_all:
            raise RuntimeError('provider unavailable')

        if 'stooq.com' in url:
            return '\n'.join(
                [
                    '^SPX,2026-02-17,11:00:00,6000,6010,5990,6005,0,S&P500',
                    '^DJI,2026-02-17,11:00:00,42000,42100,41900,42050,0,Dow Jones',
                    '^NDQ,2026-02-17,11:00:00,19000,19100,18950,19020,0,Nasdaq Comp',
                    'IWM.US,2026-02-17,11:00:00,200,201,199,200.5,0,Russell ETF',
                    'EURUSD,2026-02-17,11:00:00,1.08,1.09,1.07,1.085,0,EUR/USD',
                    'USDJPY,2026-02-17,11:00:00,150.0,150.5,149.8,150.2,0,USD/JPY',
                    'GBPUSD,2026-02-17,11:00:00,1.26,1.27,1.25,1.265,0,GBP/USD',
                    'CL.F,2026-02-17,11:00:00,72.1,72.5,71.9,72.3,0,WTI Crude',
                    'GC.F,2026-02-17,11:00:00,2350,2360,2345,2358,0,Gold',
                    'SI.F,2026-02-17,11:00:00,29.1,29.4,28.9,29.2,0,Silver',
                    'HG.F,2026-02-17,11:00:00,4.00,4.02,3.98,4.01,0,Copper',
                ]
            )

        if 'fredgraph.csv' in url:
            series_id = kwargs['params']['id']
            if series_id == 'DGS10':
                return 'DATE,DGS10\n2026-02-15,4.10\n2026-02-16,4.15\n'
            if series_id == 'DGS5':
                return 'DATE,DGS5\n2026-02-15,3.90\n2026-02-16,3.95\n'
            if series_id == 'DGS3MO':
                return 'DATE,DGS3MO\n2026-02-15,4.25\n2026-02-16,4.30\n'

        raise RuntimeError(f'unexpected get_text url: {url}')


@pytest.mark.asyncio
async def test_uses_stooq_and_fred_public_when_yahoo_fails() -> None:
    settings = Settings(
        redis_url='',
        fred_api_key=None,
        yahoo_endpoints=['https://query1.finance.yahoo.com/v7/finance/quote'],
        market_cache_ttl_seconds=1,
        market_stale_ttl_seconds=60,
    )
    service = MarketOverviewService(settings=settings, cache=FakeCache(), http_client=FakeHttp())

    response = await service.get_overview()

    assert response.degraded is True
    assert len(response.sections.indices) == 4
    assert len(response.sections.fx) == 3
    assert len(response.sections.commodities) == 4
    assert len(response.sections.rates) == 3
    assert len(response.sections.crypto) == 3

    warning_text = ' | '.join(response.warnings)
    assert 'Yahoo Finance unavailable' in warning_text
    assert 'Using Stooq fallback' in warning_text
    assert 'Using FRED public fallback' in warning_text

    provider_health = await service.get_provider_status()
    assert provider_health['providers']['yahoo']['status'] == 'degraded'
    assert provider_health['providers']['stooq']['status'] == 'ok'
    assert provider_health['providers']['fred_public']['status'] == 'ok'
    assert provider_health['providers']['coingecko']['status'] == 'ok'


@pytest.mark.asyncio
async def test_serves_stale_cache_when_all_providers_fail() -> None:
    settings = Settings(
        redis_url='',
        fred_api_key=None,
        yahoo_endpoints=['https://query1.finance.yahoo.com/v7/finance/quote'],
        market_cache_ttl_seconds=1,
        market_stale_ttl_seconds=60,
    )
    cache = FakeCache()

    stale_payload = MarketOverviewResponse(
        as_of=datetime.now(timezone.utc),
        degraded=False,
        warnings=['stale snapshot'],
        sections=MarketSections(
            crypto=[
                MarketPoint(
                    symbol='BTC-USD',
                    name='Bitcoin',
                    price=50000,
                    change=0,
                    change_percent=0,
                    currency='USD',
                    source='stale',
                )
            ]
        ),
    ).model_dump(mode='json', by_alias=True)

    cache.store['market:overview:stale'] = stale_payload

    service = MarketOverviewService(settings=settings, cache=cache, http_client=FakeHttp(fail_all=True))
    response = await service.get_overview()

    assert response.degraded is True
    assert response.sections.crypto[0].source == 'stale'
    assert any('Serving stale market cache due to provider failures.' in warning for warning in response.warnings)


@pytest.mark.asyncio
async def test_returns_degraded_empty_snapshot_when_all_providers_fail_and_no_stale_cache() -> None:
    settings = Settings(
        redis_url='',
        fred_api_key=None,
        yahoo_endpoints=['https://query1.finance.yahoo.com/v7/finance/quote'],
        market_cache_ttl_seconds=1,
        market_stale_ttl_seconds=60,
    )

    service = MarketOverviewService(settings=settings, cache=FakeCache(), http_client=FakeHttp(fail_all=True))
    response = await service.get_overview()

    assert response.degraded is True
    assert response.sections.indices == []
    assert response.sections.rates == []
    assert response.sections.fx == []
    assert response.sections.commodities == []
    assert response.sections.crypto == []
    assert any('No live market data available from providers and no stale cache was found.' in warning for warning in response.warnings)


@pytest.mark.asyncio
async def test_market_overview_endpoint_returns_200_when_all_providers_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        redis_url='',
        fred_api_key=None,
        yahoo_endpoints=['https://query1.finance.yahoo.com/v7/finance/quote'],
        market_cache_ttl_seconds=1,
        market_stale_ttl_seconds=60,
    )
    service = MarketOverviewService(settings=settings, cache=FakeCache(), http_client=FakeHttp(fail_all=True))
    container = type('Container', (), {'market_overview': service, 'settings': settings})()

    monkeypatch.setattr(market_routes, 'get_container', lambda: container)

    app = FastAPI()
    app.include_router(market_routes.router, prefix='/api/v1')

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/v1/market/overview')

    assert response.status_code == 200
    payload = response.json()
    assert payload['degraded'] is True
    assert payload['sections']['indices'] == []
    assert payload['sections']['rates'] == []
    assert payload['sections']['fx'] == []
    assert payload['sections']['commodities'] == []
    assert payload['sections']['crypto'] == []
