from __future__ import annotations

import time
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
    def __init__(
        self,
        *,
        fail_yahoo: bool = False,
        fail_stooq_primary: bool = False,
        fail_stooq_proxy: bool = False,
        fail_fred_public: bool = False,
        fail_frankfurter: bool = False,
        fail_exchangerate: bool = False,
        fail_coingecko: bool = False,
        fail_all_live: bool = False,
    ) -> None:
        self.fail_yahoo = fail_yahoo
        self.fail_stooq_primary = fail_stooq_primary
        self.fail_stooq_proxy = fail_stooq_proxy
        self.fail_fred_public = fail_fred_public
        self.fail_frankfurter = fail_frankfurter
        self.fail_exchangerate = fail_exchangerate
        self.fail_coingecko = fail_coingecko
        self.fail_all_live = fail_all_live

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        if self.fail_all_live:
            raise RuntimeError('provider unavailable')

        if 'finance.yahoo.com' in url:
            if self.fail_yahoo:
                raise RuntimeError('HTTP 429')
            return {'quoteResponse': {'result': []}}

        if 'api.frankfurter.app' in url:
            if self.fail_frankfurter:
                raise RuntimeError('frankfurter down')
            return {
                'amount': 1.0,
                'base': 'USD',
                'date': '2026-02-16',
                'rates': {'EUR': 0.92, 'JPY': 150.2, 'GBP': 0.79},
            }

        if 'exchangerate.host' in url:
            if self.fail_exchangerate:
                raise RuntimeError('exchangerate down')
            return {
                'base': 'USD',
                'date': '2026-02-16',
                'rates': {'EUR': 0.915, 'JPY': 149.9, 'GBP': 0.788},
            }

        if 'coingecko' in url:
            if self.fail_coingecko:
                raise RuntimeError('coingecko down')
            return {
                'bitcoin': {'usd': 64000.0, 'usd_24h_change': 1.2},
                'ethereum': {'usd': 3200.0, 'usd_24h_change': -0.8},
                'solana': {'usd': 120.0, 'usd_24h_change': 2.5},
            }

        raise RuntimeError(f'unexpected get_json url: {url}')

    async def get_text(self, url: str, **kwargs: Any) -> str:
        if self.fail_all_live:
            raise RuntimeError('provider unavailable')

        if 'stooq.com' in url:
            lower = url.lower()
            if '^spx' in lower:
                if self.fail_stooq_primary:
                    raise RuntimeError('stooq primary down')
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

            if 'spy.us' in lower:
                if self.fail_stooq_proxy:
                    raise RuntimeError('stooq proxy down')
                return '\n'.join(
                    [
                        'SPY.US,2026-02-17,11:00:00,600,602,598,601,0,SPY',
                        'DIA.US,2026-02-17,11:00:00,420,421,419,420.5,0,DIA',
                        'QQQ.US,2026-02-17,11:00:00,500,501,499,500.2,0,QQQ',
                        'IWM.US,2026-02-17,11:00:00,200,201,199,200.5,0,IWM',
                        'USO.US,2026-02-17,11:00:00,72,72.5,71.8,72.2,0,USO',
                        'GLD.US,2026-02-17,11:00:00,236,236.2,235.5,236.1,0,GLD',
                        'SLV.US,2026-02-17,11:00:00,29,29.3,28.8,29.1,0,SLV',
                        'CPER.US,2026-02-17,11:00:00,40,40.2,39.9,40.1,0,CPER',
                    ]
                )

        if 'fredgraph.csv' in url:
            if self.fail_fred_public:
                raise RuntimeError('fred public down')
            series_id = kwargs['params']['id']
            if series_id == 'DGS10':
                return 'DATE,DGS10\n2026-02-15,4.10\n2026-02-16,4.15\n'
            if series_id == 'DGS5':
                return 'DATE,DGS5\n2026-02-15,3.90\n2026-02-16,3.95\n'
            if series_id == 'DGS3MO':
                return 'DATE,DGS3MO\n2026-02-15,4.25\n2026-02-16,4.30\n'

        raise RuntimeError(f'unexpected get_text url: {url}')


def build_settings(*, bootstrap_enabled: bool = True, rates_defaults_enabled: bool = True) -> Settings:
    return Settings(
        redis_url='',
        fred_api_key=None,
        yahoo_endpoints=['https://query1.finance.yahoo.com/v7/finance/quote'],
        market_cache_ttl_seconds=1,
        market_stale_ttl_seconds=60,
        market_bootstrap_enabled=bootstrap_enabled,
        market_rates_defaults_enabled=rates_defaults_enabled,
    )


@pytest.mark.asyncio
async def test_yahoo_hard_fail_others_ok_sections_populated() -> None:
    service = MarketOverviewService(
        settings=build_settings(),
        cache=FakeCache(),
        http_client=FakeHttp(fail_yahoo=True),
    )

    response = await service.get_overview()

    assert len(response.sections.indices) == 4
    assert len(response.sections.fx) == 3
    assert len(response.sections.commodities) == 4
    assert len(response.sections.rates) == 3
    assert len(response.sections.crypto) == 3

    assert response.degraded is True
    assert response.banner is not None
    assert response.banner.startswith('Yahoo down, serving from')
    assert response.section_meta['indices'].source in {'Stooq', 'Stooq Proxy'}
    assert response.section_meta['rates'].source == 'FRED Public'


@pytest.mark.asyncio
async def test_yahoo_and_primary_fail_fallback_ok_sections_populated() -> None:
    service = MarketOverviewService(
        settings=build_settings(),
        cache=FakeCache(),
        http_client=FakeHttp(
            fail_yahoo=True,
            fail_stooq_primary=True,
            fail_fred_public=True,
        ),
    )

    response = await service.get_overview()

    assert len(response.sections.indices) == 4
    assert len(response.sections.fx) == 3
    assert len(response.sections.commodities) == 4
    assert len(response.sections.rates) == 3
    assert len(response.sections.crypto) == 3

    # Deterministic fallback matrix should kick in.
    assert response.section_meta['indices'].source == 'Stooq Proxy'
    assert response.section_meta['fx'].source == 'Frankfurter'
    assert response.section_meta['rates'].source in {'Default Snapshot', 'Last Known Good'}


@pytest.mark.asyncio
async def test_all_live_fail_with_lkg_available_sections_come_from_cache() -> None:
    settings = build_settings()
    cache = FakeCache()

    snapshot_time = datetime.now(timezone.utc).isoformat()
    for section, symbol in {
        'indices': '^GSPC',
        'rates': '^TNX',
        'fx': 'EURUSD=X',
        'commodities': 'CL=F',
        'crypto': 'BTC-USD',
    }.items():
        cache.store[f'market:overview:lkg:{section}'] = (
            {
                'as_of': snapshot_time,
                'points': [
                    MarketPoint(
                        symbol=symbol,
                        name=f'{section} cached point',
                        price=100.0,
                        change=0.0,
                        change_percent=0.0,
                        currency='USD',
                        source='cached-live',
                    ).model_dump(mode='json', by_alias=True)
                ],
            },
            time.time() + 300,
        )

    service = MarketOverviewService(settings=settings, cache=cache, http_client=FakeHttp(fail_all_live=True))
    response = await service.get_overview()

    assert response.degraded is True
    assert response.sections.indices[0].source.startswith('lkg:')
    assert response.sections.rates[0].source.startswith('lkg:')
    assert response.sections.fx[0].source.startswith('lkg:')
    assert response.sections.commodities[0].source.startswith('lkg:')
    assert response.sections.crypto[0].source.startswith('lkg:')


@pytest.mark.asyncio
async def test_all_fail_no_lkg_bootstrap_disabled_returns_graceful_empty_200() -> None:
    settings = build_settings(bootstrap_enabled=False, rates_defaults_enabled=False)
    service = MarketOverviewService(settings=settings, cache=FakeCache(), http_client=FakeHttp(fail_all_live=True))

    response = await service.get_overview()

    assert response.degraded is True
    assert response.sections.indices == []
    assert response.sections.rates == []
    assert response.sections.fx == []
    assert response.sections.commodities == []
    assert response.sections.crypto == []
    assert any('No live market data available' in warning for warning in response.warnings)


@pytest.mark.asyncio
async def test_market_overview_endpoint_returns_populated_sections_when_yahoo_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = build_settings()
    service = MarketOverviewService(settings=settings, cache=FakeCache(), http_client=FakeHttp(fail_yahoo=True))
    container = type('Container', (), {'market_overview': service, 'settings': settings})()

    monkeypatch.setattr(market_routes, 'get_container', lambda: container)

    app = FastAPI()
    app.include_router(market_routes.router, prefix='/api/v1')

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/v1/market/overview')

    assert response.status_code == 200
    payload = response.json()
    assert payload['sections']['indices']
    assert payload['sections']['rates']
    assert payload['sections']['fx']
    assert payload['sections']['commodities']
    assert payload['sections']['crypto']
