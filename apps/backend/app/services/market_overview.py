from __future__ import annotations

import asyncio
import csv
import io
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from app.core.config import Settings
from app.schemas.market import MarketOverviewResponse, MarketPoint, MarketSectionMeta, MarketSections
from app.services.cache import CacheClient
from app.services.http_client import HttpClient, HttpRequestError
from app.services.rate_limiter import AsyncRateLimiter

logger = logging.getLogger(__name__)

SectionName = Literal['indices', 'rates', 'fx', 'commodities', 'crypto']
ProviderName = Literal[
    'yahoo',
    'stooq',
    'stooq_proxy',
    'frankfurter',
    'exchangerate_host',
    'fred_api',
    'fred_public',
    'rates_defaults',
    'coingecko',
    'lkg',
    'bootstrap',
]

SECTION_TARGETS: dict[SectionName, list[tuple[str, str, str | None]]] = {
    'indices': [
        ('^GSPC', 'S&P 500', 'USD'),
        ('^DJI', 'Dow Jones Industrial Average', 'USD'),
        ('^IXIC', 'Nasdaq Composite', 'USD'),
        ('^RUT', 'Russell 2000', 'USD'),
    ],
    'rates': [
        ('^TNX', 'US 10Y Treasury Yield', 'PCT'),
        ('^FVX', 'US 5Y Treasury Yield', 'PCT'),
        ('^IRX', 'US 13W Treasury Yield', 'PCT'),
    ],
    'fx': [
        ('EURUSD=X', 'EUR/USD', 'USD'),
        ('USDJPY=X', 'USD/JPY', 'JPY'),
        ('GBPUSD=X', 'GBP/USD', 'USD'),
    ],
    'commodities': [
        ('CL=F', 'WTI Crude Oil', 'USD'),
        ('GC=F', 'Gold', 'USD'),
        ('SI=F', 'Silver', 'USD'),
        ('HG=F', 'Copper', 'USD'),
    ],
    'crypto': [
        ('BTC-USD', 'Bitcoin', 'USD'),
        ('ETH-USD', 'Ethereum', 'USD'),
        ('SOL-USD', 'Solana', 'USD'),
    ],
}

# Yahoo is optional/augmenting for core sections.
YAHOO_SYMBOLS: list[tuple[SectionName, str, str]] = [
    (section, symbol, name)
    for section, values in SECTION_TARGETS.items()
    for symbol, name, _ in values
]

# Primary non-Yahoo sources.
STOOQ_PRIMARY_SYMBOLS: list[tuple[SectionName, str, str, str, str | None]] = [
    ('indices', '^spx', '^GSPC', 'S&P 500', 'USD'),
    ('indices', '^dji', '^DJI', 'Dow Jones Industrial Average', 'USD'),
    ('indices', '^ndq', '^IXIC', 'Nasdaq Composite', 'USD'),
    ('indices', 'iwm.us', '^RUT', 'Russell 2000 (ETF Proxy)', 'USD'),
    ('fx', 'eurusd', 'EURUSD=X', 'EUR/USD', 'USD'),
    ('fx', 'usdjpy', 'USDJPY=X', 'USD/JPY', 'JPY'),
    ('fx', 'gbpusd', 'GBPUSD=X', 'GBP/USD', 'USD'),
    ('commodities', 'cl.f', 'CL=F', 'WTI Crude Oil', 'USD'),
    ('commodities', 'gc.f', 'GC=F', 'Gold', 'USD'),
    ('commodities', 'si.f', 'SI=F', 'Silver', 'USD'),
    ('commodities', 'hg.f', 'HG=F', 'Copper', 'USD'),
]

# Stable mapped fallbacks for indices + commodities (ETF proxies).
STOOQ_PROXY_SYMBOLS: list[tuple[SectionName, str, str, str, str | None]] = [
    ('indices', 'spy.us', '^GSPC', 'S&P 500 (SPY Proxy)', 'USD'),
    ('indices', 'dia.us', '^DJI', 'Dow Jones (DIA Proxy)', 'USD'),
    ('indices', 'qqq.us', '^IXIC', 'Nasdaq Composite (QQQ Proxy)', 'USD'),
    ('indices', 'iwm.us', '^RUT', 'Russell 2000 (IWM Proxy)', 'USD'),
    ('commodities', 'uso.us', 'CL=F', 'WTI Crude (USO Proxy)', 'USD'),
    ('commodities', 'gld.us', 'GC=F', 'Gold (GLD Proxy)', 'USD'),
    ('commodities', 'slv.us', 'SI=F', 'Silver (SLV Proxy)', 'USD'),
    ('commodities', 'cper.us', 'HG=F', 'Copper (CPER Proxy)', 'USD'),
]

FRED_SERIES: list[tuple[str, str, str]] = [
    ('DGS10', '^TNX', 'US 10Y Treasury Yield'),
    ('DGS5', '^FVX', 'US 5Y Treasury Yield'),
    ('DGS3MO', '^IRX', 'US 13W Treasury Yield'),
]

RATES_DEFAULT_SNAPSHOT: list[tuple[str, str, float, str]] = [
    ('^TNX', 'US 10Y Treasury Yield (Default Snapshot)', 4.15, 'PCT'),
    ('^FVX', 'US 5Y Treasury Yield (Default Snapshot)', 3.95, 'PCT'),
    ('^IRX', 'US 13W Treasury Yield (Default Snapshot)', 4.30, 'PCT'),
]

BOOTSTRAP_SNAPSHOT: dict[SectionName, list[tuple[str, str, float, str | None]]] = {
    'indices': [
        ('^GSPC', 'S&P 500 (Bootstrap)', 5980.0, 'USD'),
        ('^DJI', 'Dow Jones (Bootstrap)', 41850.0, 'USD'),
        ('^IXIC', 'Nasdaq Composite (Bootstrap)', 18950.0, 'USD'),
        ('^RUT', 'Russell 2000 (Bootstrap)', 2065.0, 'USD'),
    ],
    'rates': [
        ('^TNX', 'US 10Y Treasury Yield (Bootstrap)', 4.12, 'PCT'),
        ('^FVX', 'US 5Y Treasury Yield (Bootstrap)', 3.90, 'PCT'),
        ('^IRX', 'US 13W Treasury Yield (Bootstrap)', 4.22, 'PCT'),
    ],
    'fx': [
        ('EURUSD=X', 'EUR/USD (Bootstrap)', 1.0850, 'USD'),
        ('USDJPY=X', 'USD/JPY (Bootstrap)', 150.0, 'JPY'),
        ('GBPUSD=X', 'GBP/USD (Bootstrap)', 1.2680, 'USD'),
    ],
    'commodities': [
        ('CL=F', 'WTI Crude Oil (Bootstrap)', 72.4, 'USD'),
        ('GC=F', 'Gold (Bootstrap)', 2355.0, 'USD'),
        ('SI=F', 'Silver (Bootstrap)', 29.2, 'USD'),
        ('HG=F', 'Copper (Bootstrap)', 4.01, 'USD'),
    ],
    'crypto': [
        ('BTC-USD', 'Bitcoin (Bootstrap)', 64000.0, 'USD'),
        ('ETH-USD', 'Ethereum (Bootstrap)', 3200.0, 'USD'),
        ('SOL-USD', 'Solana (Bootstrap)', 120.0, 'USD'),
    ],
}

SECTION_PROVIDER_MATRIX: dict[SectionName, tuple[ProviderName, ...]] = {
    'indices': ('stooq', 'stooq_proxy', 'yahoo', 'lkg', 'bootstrap'),
    'fx': ('stooq', 'frankfurter', 'exchangerate_host', 'yahoo', 'lkg', 'bootstrap'),
    'commodities': ('stooq', 'stooq_proxy', 'yahoo', 'lkg', 'bootstrap'),
    'rates': ('fred_public', 'fred_api', 'lkg', 'rates_defaults', 'bootstrap'),
    'crypto': ('coingecko', 'yahoo', 'lkg', 'bootstrap'),
}

PROVIDER_LABELS: dict[ProviderName, str] = {
    'yahoo': 'Yahoo',
    'stooq': 'Stooq',
    'stooq_proxy': 'Stooq Proxy',
    'frankfurter': 'Frankfurter',
    'exchangerate_host': 'ExchangeRate.host',
    'fred_api': 'FRED API',
    'fred_public': 'FRED Public',
    'rates_defaults': 'Default Snapshot',
    'coingecko': 'CoinGecko',
    'lkg': 'Last Known Good',
    'bootstrap': 'Bootstrap Snapshot',
}

LIVE_PROVIDERS: set[ProviderName] = {
    'yahoo',
    'stooq',
    'stooq_proxy',
    'frankfurter',
    'exchangerate_host',
    'fred_api',
    'fred_public',
    'coingecko',
}

INTERNAL_PROVIDERS: set[ProviderName] = {'lkg', 'bootstrap', 'rates_defaults'}

EXPECTED_SECTION_COUNTS: dict[SectionName, int] = {
    section: len(points) for section, points in SECTION_TARGETS.items()
}


class MarketOverviewService:
    def __init__(self, settings: Settings, cache: CacheClient, http_client: HttpClient) -> None:
        self.settings = settings
        self.cache = cache
        self.http = http_client
        self.yahoo_limiter = AsyncRateLimiter(max_calls=settings.yahoo_rate_limit_per_minute, period_seconds=60)
        self.stooq_limiter = AsyncRateLimiter(max_calls=settings.stooq_rate_limit_per_minute, period_seconds=60)
        self.fx_limiter = AsyncRateLimiter(max_calls=settings.fx_rate_limit_per_minute, period_seconds=60)
        self.coingecko_limiter = AsyncRateLimiter(max_calls=settings.coingecko_rate_limit_per_minute, period_seconds=60)
        self.fred_limiter = AsyncRateLimiter(max_calls=settings.fred_rate_limit_per_minute, period_seconds=60)

        self._provider_lock = asyncio.Lock()
        self._overview_refresh_lock = asyncio.Lock()
        self._provider_status: dict[str, dict[str, Any]] = {
            'yahoo': self._new_provider_state(),
            'stooq': self._new_provider_state(),
            'stooq_proxy': self._new_provider_state(),
            'frankfurter': self._new_provider_state(),
            'exchangerate_host': self._new_provider_state(),
            'fred_api': self._new_provider_state(status='disabled' if not settings.fred_api_key else 'unknown'),
            'fred_public': self._new_provider_state(),
            'coingecko': self._new_provider_state(),
            'lkg': self._new_provider_state(status='internal'),
            'bootstrap': self._new_provider_state(status='internal' if settings.market_bootstrap_enabled else 'disabled'),
            'rates_defaults': self._new_provider_state(status='internal'),
        }

    async def get_overview(self) -> MarketOverviewResponse:
        fresh_key = 'market:overview:fresh'
        stale_key = 'market:overview:stale'
        upstream_key = 'market:overview:upstream'

        cached_fresh = await self.cache.get(fresh_key)
        if cached_fresh is not None:
            return MarketOverviewResponse.model_validate(cached_fresh)

        upstream_response, upstream_fetched_at = await self._load_upstream_snapshot(upstream_key)
        if not self._should_refresh_live(upstream_response, upstream_fetched_at):
            return await self._serve_upstream_snapshot(fresh_key, upstream_response)

        async with self._overview_refresh_lock:
            cached_fresh = await self.cache.get(fresh_key)
            if cached_fresh is not None:
                return MarketOverviewResponse.model_validate(cached_fresh)

            upstream_response, upstream_fetched_at = await self._load_upstream_snapshot(upstream_key)
            if not self._should_refresh_live(upstream_response, upstream_fetched_at):
                return await self._serve_upstream_snapshot(fresh_key, upstream_response)

            return await self._refresh_overview(fresh_key=fresh_key, stale_key=stale_key, upstream_key=upstream_key)

    async def _load_upstream_snapshot(
        self,
        upstream_key: str,
    ) -> tuple[MarketOverviewResponse | None, datetime | None]:
        upstream_payload = await self.cache.get(upstream_key)
        if not isinstance(upstream_payload, dict):
            return None, None

        upstream_response: MarketOverviewResponse | None = None

        payload_raw = upstream_payload.get('payload')
        if payload_raw is not None:
            try:
                upstream_response = MarketOverviewResponse.model_validate(payload_raw)
            except Exception:
                upstream_response = None

        upstream_fetched_at = self._parse_dt(upstream_payload.get('fetchedAt'))
        return upstream_response, upstream_fetched_at

    def _should_refresh_live(
        self,
        upstream_response: MarketOverviewResponse | None,
        upstream_fetched_at: datetime | None,
    ) -> bool:
        now = datetime.now(timezone.utc)
        return (
            upstream_response is None
            or upstream_fetched_at is None
            or (now - upstream_fetched_at).total_seconds() >= self.settings.market_upstream_refresh_seconds
        )

    async def _serve_upstream_snapshot(
        self,
        fresh_key: str,
        upstream_response: MarketOverviewResponse | None,
    ) -> MarketOverviewResponse:
        if upstream_response is None:
            raise RuntimeError('upstream response is missing')

        serialized = upstream_response.model_dump(mode='json', by_alias=True)
        await self.cache.set(fresh_key, serialized, ttl_seconds=self.settings.market_cache_ttl_seconds)
        return upstream_response

    async def _refresh_overview(
        self,
        *,
        fresh_key: str,
        stale_key: str,
        upstream_key: str,
    ) -> MarketOverviewResponse:
        provider_payload_cache: dict[str, dict[SectionName, list[MarketPoint]] | None] = {}

        async def provider_payload(provider: ProviderName) -> dict[SectionName, list[MarketPoint]] | None:
            if provider in provider_payload_cache:
                return provider_payload_cache[provider]

            payload: dict[SectionName, list[MarketPoint]] | None
            if provider == 'yahoo':
                payload = await self._run_provider('yahoo', self._fetch_yahoo_sections)
            elif provider == 'stooq':
                payload = await self._run_provider('stooq', self._fetch_stooq_primary_sections)
            elif provider == 'stooq_proxy':
                payload = await self._run_provider('stooq_proxy', self._fetch_stooq_proxy_sections)
            elif provider == 'frankfurter':
                payload = await self._run_provider('frankfurter', self._fetch_frankfurter_fx)
            elif provider == 'exchangerate_host':
                payload = await self._run_provider('exchangerate_host', self._fetch_exchangerate_host_fx)
            elif provider == 'fred_api':
                payload = await self._run_provider('fred_api', self._fetch_fred_api_rates)
            elif provider == 'fred_public':
                payload = await self._run_provider('fred_public', self._fetch_fred_public_rates)
            elif provider == 'coingecko':
                payload = await self._run_provider('coingecko', self._fetch_coingecko_crypto)
            else:
                payload = None

            provider_payload_cache[provider] = payload
            return payload

        # Optional Yahoo probe for banner/circuit-breaker tracking. Not required for section population.
        await provider_payload('yahoo')

        sections = MarketSections()
        section_meta: dict[str, MarketSectionMeta] = {}
        critical_warnings: list[str] = []
        total_live_points = 0

        for section in ('indices', 'rates', 'fx', 'commodities', 'crypto'):
            points, meta, used_live = await self._build_section(section, provider_payload)
            setattr(sections, section, points)
            section_meta[section] = meta

            if points and used_live:
                total_live_points += len(points)
                await self._persist_lkg_section(section, points)

            if meta.loaded == 0:
                critical_warnings.append(f'No {section} data available from live providers or cache.')
            elif meta.loaded < meta.expected:
                critical_warnings.append(f'Partial {section} coverage ({meta.loaded}/{meta.expected}).')

        total_points = sum(meta.loaded for meta in section_meta.values())
        stale_sections = [name for name, meta in section_meta.items() if meta.stale and meta.loaded > 0]

        if total_points == 0:
            stale_payload = await self.cache.get(stale_key)
            if stale_payload is not None:
                stale_model = MarketOverviewResponse.model_validate(stale_payload)
                stale_warnings = list(stale_model.warnings)
                stale_warnings.extend(critical_warnings)
                stale_warnings.append('Serving stale overview snapshot due to provider failures.')
                banner = stale_model.banner or 'All live providers unavailable, serving stale snapshot.'
                return stale_model.model_copy(
                    update={
                        'degraded': True,
                        'banner': banner,
                        'warnings': self._dedupe(stale_warnings),
                    }
                )

            critical_warnings = ['No live market data available from providers, cache, or bootstrap snapshot.']

        if stale_sections and total_live_points == 0:
            critical_warnings.append('Live providers unavailable; data served from cache/default snapshots.')

        banner = await self._build_banner(section_meta, total_points)
        degraded = bool(banner or critical_warnings or stale_sections)

        response = MarketOverviewResponse(
            as_of=datetime.now(timezone.utc),
            degraded=degraded,
            banner=banner,
            warnings=self._dedupe(critical_warnings),
            sections=sections,
            section_meta=section_meta,
        )

        serialized = response.model_dump(mode='json', by_alias=True)
        await self.cache.set(fresh_key, serialized, ttl_seconds=self.settings.market_cache_ttl_seconds)
        await self.cache.set(stale_key, serialized, ttl_seconds=self.settings.market_stale_ttl_seconds)
        await self.cache.set(
            upstream_key,
            {
                'fetchedAt': datetime.now(timezone.utc).isoformat(),
                'payload': serialized,
            },
            ttl_seconds=self.settings.market_stale_ttl_seconds,
        )

        return response

    async def get_provider_status(self) -> dict[str, Any]:
        async with self._provider_lock:
            providers = {name: dict(state) for name, state in self._provider_status.items()}

        overall = 'ok'
        if any(state.get('status') in {'degraded', 'cooldown'} for state in providers.values()):
            overall = 'degraded'

        return {
            'as_of': datetime.now(timezone.utc).isoformat(),
            'status': overall,
            'providers': providers,
            'matrix': SECTION_PROVIDER_MATRIX,
        }

    async def _build_section(
        self,
        section: SectionName,
        provider_loader: Any,
    ) -> tuple[list[MarketPoint], MarketSectionMeta, bool]:
        expected_symbols = {symbol for symbol, _, _ in SECTION_TARGETS[section]}
        points: list[MarketPoint] = []
        provider_chain: list[ProviderName] = []

        for provider in SECTION_PROVIDER_MATRIX[section]:
            if len(points) >= EXPECTED_SECTION_COUNTS[section]:
                break

            candidates = await self._section_candidates_from_provider(section, provider, provider_loader)
            if not candidates:
                continue

            added = self._merge_missing_target_points(points, candidates, expected_symbols)
            if added > 0:
                provider_chain.append(provider)

        points = self._order_section_points(section, points)

        source = PROVIDER_LABELS[provider_chain[0]] if provider_chain else None
        sources = [PROVIDER_LABELS[name] for name in provider_chain]
        section_as_of = self._latest_as_of(points)
        stale = any(provider in INTERNAL_PROVIDERS for provider in provider_chain)
        used_live = any(provider in LIVE_PROVIDERS for provider in provider_chain)

        meta = MarketSectionMeta(
            source=source,
            sources=sources,
            as_of=section_as_of,
            loaded=len(points),
            expected=EXPECTED_SECTION_COUNTS[section],
            stale=stale,
        )

        return points, meta, used_live

    async def _section_candidates_from_provider(
        self,
        section: SectionName,
        provider: ProviderName,
        provider_loader: Any,
    ) -> list[MarketPoint]:
        if provider == 'lkg':
            return await self._load_lkg_section(section)

        if provider == 'bootstrap':
            return self._bootstrap_section_points(section)

        if provider == 'rates_defaults':
            return self._build_rates_default_points()

        payload = await provider_loader(provider)
        if payload is None:
            return []

        return list(payload.get(section, []))

    async def _run_provider(
        self,
        provider: ProviderName,
        fetcher: Any,
    ) -> dict[SectionName, list[MarketPoint]] | None:
        if not await self._provider_call_allowed(provider):
            return None

        try:
            payload = await fetcher()
            if not self._has_any_provider_payload(payload):
                raise RuntimeError('provider returned empty payload')
            await self._record_provider_result(provider, success=True)
            return payload
        except Exception as exc:
            await self._record_provider_result(provider, success=False, error=self._summarize_error(exc))
            return None

    async def _provider_call_allowed(self, provider: ProviderName) -> bool:
        async with self._provider_lock:
            state = self._provider_status.setdefault(provider, self._new_provider_state())

            if state.get('status') == 'disabled':
                return False

            if provider == 'fred_api' and not self.settings.fred_api_key:
                state['status'] = 'disabled'
                return False

            cooldown_until = self._parse_dt(state.get('cooldown_until'))
            now = datetime.now(timezone.utc)

            if cooldown_until and cooldown_until > now:
                state['status'] = 'cooldown'
                return False

            if cooldown_until and cooldown_until <= now:
                state['cooldown_until'] = None
                state['consecutive_failures'] = 0
                if state.get('status') == 'cooldown':
                    state['status'] = 'unknown'

        return True

    async def _record_provider_result(self, provider: ProviderName, *, success: bool, error: str | None = None) -> None:
        async with self._provider_lock:
            state = self._provider_status.setdefault(provider, self._new_provider_state())
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()
            state['last_attempt_at'] = now_iso

            if success:
                state['status'] = 'ok'
                state['last_success_at'] = now_iso
                state['last_error'] = None
                state['success_count'] = int(state.get('success_count', 0)) + 1
                state['consecutive_failures'] = 0
                state['cooldown_until'] = None
                return

            if state.get('status') == 'disabled':
                return

            state['failure_count'] = int(state.get('failure_count', 0)) + 1
            failures = int(state.get('consecutive_failures', 0)) + 1
            state['consecutive_failures'] = failures
            state['last_error'] = error or 'unknown error'

            threshold = self.settings.yahoo_failure_threshold if provider == 'yahoo' else self.settings.provider_failure_threshold
            cooldown_seconds = (
                self.settings.yahoo_cooldown_seconds if provider == 'yahoo' else self.settings.provider_cooldown_seconds
            )

            if failures >= threshold:
                state['status'] = 'cooldown'
                state['cooldown_until'] = (now + timedelta(seconds=cooldown_seconds)).isoformat()
            else:
                state['status'] = 'degraded'

    @staticmethod
    def _new_provider_state(status: str = 'unknown') -> dict[str, Any]:
        return {
            'status': status,
            'last_attempt_at': None,
            'last_success_at': None,
            'last_error': None,
            'success_count': 0,
            'failure_count': 0,
            'consecutive_failures': 0,
            'cooldown_until': None,
        }

    async def _build_banner(self, section_meta: dict[str, MarketSectionMeta], total_points: int) -> str | None:
        yahoo_status = await self._provider_state_status('yahoo')

        if yahoo_status in {'degraded', 'cooldown'} and total_points > 0:
            fallback_sources = [
                meta.source
                for meta in section_meta.values()
                if meta.source and meta.source not in {'Yahoo', 'Last Known Good', 'Bootstrap Snapshot'}
            ]
            fallback_sources = self._dedupe(fallback_sources)
            source_text = '/'.join(fallback_sources) if fallback_sources else 'fallback providers'
            return f'Yahoo down, serving from {source_text}.'

        return None

    async def _provider_state_status(self, provider: str) -> str:
        async with self._provider_lock:
            return str(self._provider_status.get(provider, {}).get('status') or 'unknown')

    async def _persist_lkg_section(self, section: SectionName, points: list[MarketPoint]) -> None:
        key = f'market:overview:lkg:{section}'
        payload = {
            'as_of': datetime.now(timezone.utc).isoformat(),
            'points': [point.model_dump(mode='json', by_alias=True) for point in points],
        }
        await self.cache.set(key, payload, ttl_seconds=self.settings.market_lkg_ttl_seconds)

        async with self._provider_lock:
            state = self._provider_status.setdefault('lkg', self._new_provider_state(status='internal'))
            state['status'] = 'internal'
            state['last_success_at'] = payload['as_of']
            state['success_count'] = int(state.get('success_count', 0)) + 1

    async def _load_lkg_section(self, section: SectionName) -> list[MarketPoint]:
        key = f'market:overview:lkg:{section}'
        payload = await self.cache.get(key)
        if not isinstance(payload, dict):
            return []

        points_raw = payload.get('points')
        if not isinstance(points_raw, list):
            return []

        snapshot_as_of = self._parse_dt(payload.get('as_of'))
        points: list[MarketPoint] = []

        for item in points_raw:
            try:
                point = MarketPoint.model_validate(item)
            except Exception:
                continue

            source = point.source or 'unknown'
            points.append(
                point.model_copy(
                    update={
                        'source': f'lkg:{source}',
                        'as_of': snapshot_as_of or point.as_of,
                    }
                )
            )

        if points:
            async with self._provider_lock:
                state = self._provider_status.setdefault('lkg', self._new_provider_state(status='internal'))
                state['status'] = 'internal'
                state['last_success_at'] = datetime.now(timezone.utc).isoformat()

        return points

    def _bootstrap_section_points(self, section: SectionName) -> list[MarketPoint]:
        if not self.settings.market_bootstrap_enabled:
            return []

        snapshot_as_of = datetime.now(timezone.utc)
        return [
            MarketPoint(
                symbol=symbol,
                name=name,
                price=price,
                change=0.0,
                change_percent=0.0,
                currency=currency,
                source='bootstrap',
                as_of=snapshot_as_of,
            )
            for symbol, name, price, currency in BOOTSTRAP_SNAPSHOT[section]
        ]

    def _build_rates_default_points(self) -> list[MarketPoint]:
        if not self.settings.market_rates_defaults_enabled:
            return []

        snapshot_as_of = datetime.now(timezone.utc)
        return [
            MarketPoint(
                symbol=symbol,
                name=name,
                price=value,
                change=0.0,
                change_percent=0.0,
                currency=currency,
                source='rates-default',
                as_of=snapshot_as_of,
            )
            for symbol, name, value, currency in RATES_DEFAULT_SNAPSHOT
        ]

    async def _fetch_yahoo_sections(self) -> dict[SectionName, list[MarketPoint]]:
        symbols = ','.join(symbol for _, symbol, _ in YAHOO_SYMBOLS)
        headers = {
            'Accept': 'application/json,text/plain,*/*',
            'Accept-Language': self.settings.yahoo_accept_language,
            'Origin': 'https://finance.yahoo.com',
            'Referer': 'https://finance.yahoo.com/',
            'User-Agent': self.settings.yahoo_user_agent,
        }

        errors: list[str] = []

        for endpoint in self.settings.yahoo_endpoints:
            await self.yahoo_limiter.acquire()

            try:
                payload = await self.http.get_json(
                    endpoint,
                    params={'symbols': symbols},
                    headers=headers,
                    timeout=self.settings.yahoo_timeout_seconds,
                    retries=self.settings.yahoo_max_retries,
                )
            except Exception as exc:
                errors.append(f'{endpoint}: {self._summarize_error(exc)}')
                continue

            sections = self._parse_yahoo_payload(payload)
            if self._has_any_provider_payload(sections):
                return sections

            errors.append(f'{endpoint}: empty quote payload')

        raise RuntimeError('; '.join(errors) if errors else 'no Yahoo endpoint returned data')

    def _parse_yahoo_payload(self, payload: dict[str, Any]) -> dict[SectionName, list[MarketPoint]]:
        quote_response = payload.get('quoteResponse')
        if not isinstance(quote_response, dict):
            raise RuntimeError('unexpected Yahoo response shape')

        result = quote_response.get('result')
        if not isinstance(result, list):
            raise RuntimeError('Yahoo quote result missing')

        by_symbol: dict[str, dict[str, Any]] = {}
        for item in result:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get('symbol') or '').upper()
            if symbol:
                by_symbol[symbol] = item

        fetch_time = datetime.now(timezone.utc)
        sections = self._empty_payload()

        for section, symbol, default_name in YAHOO_SYMBOLS:
            row = by_symbol.get(symbol.upper())
            if not row:
                continue

            price = self._safe_float(row.get('regularMarketPrice'))
            if price is None:
                continue

            change = self._safe_float(row.get('regularMarketChange')) or 0.0
            change_percent = self._safe_float(row.get('regularMarketChangePercent')) or 0.0

            sections[section].append(
                MarketPoint(
                    symbol=symbol,
                    name=row.get('shortName') or row.get('longName') or default_name,
                    price=price,
                    change=change,
                    change_percent=change_percent,
                    currency=row.get('currency'),
                    source='yahoo',
                    as_of=fetch_time,
                )
            )

        return sections

    async def _fetch_stooq_primary_sections(self) -> dict[SectionName, list[MarketPoint]]:
        return await self._fetch_stooq_mapped_sections(STOOQ_PRIMARY_SYMBOLS, source='stooq')

    async def _fetch_stooq_proxy_sections(self) -> dict[SectionName, list[MarketPoint]]:
        return await self._fetch_stooq_mapped_sections(STOOQ_PROXY_SYMBOLS, source='stooq-proxy')

    async def _fetch_stooq_mapped_sections(
        self,
        mappings: list[tuple[SectionName, str, str, str, str | None]],
        *,
        source: str,
    ) -> dict[SectionName, list[MarketPoint]]:
        await self.stooq_limiter.acquire()

        symbols = '+'.join(symbol for _, symbol, _, _, _ in mappings)
        stooq_url = f'https://stooq.com/q/l/?s={symbols}&f=sd2t2ohlcvn&e=csv'
        csv_payload = await self.http.get_text(
            stooq_url,
            headers={
                'Accept': 'text/csv,*/*;q=0.8',
                'User-Agent': self.settings.yahoo_user_agent,
            },
            timeout=self.settings.stooq_timeout_seconds,
            retries=2,
        )

        rows = [row for row in csv.reader(io.StringIO(csv_payload)) if row]
        by_symbol: dict[str, list[str]] = {}
        for row in rows:
            key = (row[0] or '').strip().upper()
            if not key or key == 'SYMBOL':
                continue
            by_symbol[key] = row

        sections = self._empty_payload()
        fetch_time = datetime.now(timezone.utc)

        for section, stooq_symbol, output_symbol, default_name, currency in mappings:
            row = by_symbol.get(stooq_symbol.upper())
            if not row:
                continue

            open_price = self._safe_float(row[3] if len(row) > 3 else None)
            close_price = self._safe_float(row[6] if len(row) > 6 else None)
            if close_price is None:
                continue

            change = 0.0
            change_percent = 0.0
            if open_price and open_price != 0:
                change = close_price - open_price
                change_percent = (change / open_price) * 100

            label = (row[8] if len(row) > 8 else '') or default_name
            label = label if label not in {'N/D', output_symbol} else default_name

            sections[section].append(
                MarketPoint(
                    symbol=output_symbol,
                    name=label,
                    price=close_price,
                    change=change,
                    change_percent=change_percent,
                    currency=currency,
                    source=source,
                    as_of=fetch_time,
                )
            )

        if not self._has_any_provider_payload(sections):
            raise RuntimeError('Stooq returned no usable rows')

        return sections

    async def _fetch_frankfurter_fx(self) -> dict[SectionName, list[MarketPoint]]:
        await self.fx_limiter.acquire()

        payload = await self.http.get_json(
            'https://api.frankfurter.app/latest',
            params={'from': 'USD', 'to': 'EUR,JPY,GBP'},
            timeout=self.settings.fx_timeout_seconds,
            retries=1,
        )

        rates = payload.get('rates', {}) if isinstance(payload, dict) else {}
        if not isinstance(rates, dict):
            raise RuntimeError('Frankfurter rates payload malformed')

        usd_to_eur = self._safe_float(rates.get('EUR'))
        usd_to_jpy = self._safe_float(rates.get('JPY'))
        usd_to_gbp = self._safe_float(rates.get('GBP'))

        as_of = self._parse_date_to_utc(payload.get('date')) if isinstance(payload, dict) else None
        as_of = as_of or datetime.now(timezone.utc)

        fx_points: list[MarketPoint] = []
        if usd_to_eur and usd_to_eur != 0:
            fx_points.append(
                MarketPoint(
                    symbol='EURUSD=X',
                    name='EUR/USD (Frankfurter)',
                    price=1 / usd_to_eur,
                    change=0,
                    change_percent=0,
                    currency='USD',
                    source='frankfurter',
                    as_of=as_of,
                )
            )

        if usd_to_jpy:
            fx_points.append(
                MarketPoint(
                    symbol='USDJPY=X',
                    name='USD/JPY (Frankfurter)',
                    price=usd_to_jpy,
                    change=0,
                    change_percent=0,
                    currency='JPY',
                    source='frankfurter',
                    as_of=as_of,
                )
            )

        if usd_to_gbp and usd_to_gbp != 0:
            fx_points.append(
                MarketPoint(
                    symbol='GBPUSD=X',
                    name='GBP/USD (Frankfurter)',
                    price=1 / usd_to_gbp,
                    change=0,
                    change_percent=0,
                    currency='USD',
                    source='frankfurter',
                    as_of=as_of,
                )
            )

        if not fx_points:
            raise RuntimeError('Frankfurter returned no usable FX quotes')

        sections = self._empty_payload()
        sections['fx'] = fx_points
        return sections

    async def _fetch_exchangerate_host_fx(self) -> dict[SectionName, list[MarketPoint]]:
        await self.fx_limiter.acquire()

        payload = await self.http.get_json(
            'https://api.exchangerate.host/latest',
            params={'base': 'USD', 'symbols': 'EUR,JPY,GBP'},
            timeout=self.settings.fx_timeout_seconds,
            retries=1,
        )

        rates = payload.get('rates', {}) if isinstance(payload, dict) else {}
        if not isinstance(rates, dict):
            raise RuntimeError('ExchangeRate.host rates payload malformed')

        usd_to_eur = self._safe_float(rates.get('EUR'))
        usd_to_jpy = self._safe_float(rates.get('JPY'))
        usd_to_gbp = self._safe_float(rates.get('GBP'))

        as_of = self._parse_date_to_utc(payload.get('date')) if isinstance(payload, dict) else None
        as_of = as_of or datetime.now(timezone.utc)

        fx_points: list[MarketPoint] = []
        if usd_to_eur and usd_to_eur != 0:
            fx_points.append(
                MarketPoint(
                    symbol='EURUSD=X',
                    name='EUR/USD (ExchangeRate.host)',
                    price=1 / usd_to_eur,
                    change=0,
                    change_percent=0,
                    currency='USD',
                    source='exchangerate.host',
                    as_of=as_of,
                )
            )

        if usd_to_jpy:
            fx_points.append(
                MarketPoint(
                    symbol='USDJPY=X',
                    name='USD/JPY (ExchangeRate.host)',
                    price=usd_to_jpy,
                    change=0,
                    change_percent=0,
                    currency='JPY',
                    source='exchangerate.host',
                    as_of=as_of,
                )
            )

        if usd_to_gbp and usd_to_gbp != 0:
            fx_points.append(
                MarketPoint(
                    symbol='GBPUSD=X',
                    name='GBP/USD (ExchangeRate.host)',
                    price=1 / usd_to_gbp,
                    change=0,
                    change_percent=0,
                    currency='USD',
                    source='exchangerate.host',
                    as_of=as_of,
                )
            )

        if not fx_points:
            raise RuntimeError('ExchangeRate.host returned no usable FX quotes')

        sections = self._empty_payload()
        sections['fx'] = fx_points
        return sections

    async def _fetch_fred_api_rates(self) -> dict[SectionName, list[MarketPoint]]:
        if not self.settings.fred_api_key:
            return self._empty_payload()

        await self.fred_limiter.acquire()

        rates: list[MarketPoint] = []
        for series_id, symbol, label in FRED_SERIES:
            payload = await self.http.get_json(
                'https://api.stlouisfed.org/fred/series/observations',
                params={
                    'series_id': series_id,
                    'api_key': self.settings.fred_api_key,
                    'file_type': 'json',
                    'sort_order': 'desc',
                    'limit': 3,
                },
                timeout=self.settings.fred_timeout_seconds,
                retries=1,
            )

            observations = payload.get('observations', []) if isinstance(payload, dict) else []
            latest = next((item for item in observations if self._safe_float(item.get('value')) is not None), None)
            previous = next((item for item in observations[1:] if self._safe_float(item.get('value')) is not None), None)

            if latest is None:
                continue

            latest_value = self._safe_float(latest.get('value'))
            previous_value = self._safe_float(previous.get('value')) if previous else latest_value
            if latest_value is None:
                continue

            previous_value = latest_value if previous_value is None else previous_value
            as_of = self._parse_date_to_utc(latest.get('date')) or datetime.now(timezone.utc)

            rates.append(
                MarketPoint(
                    symbol=symbol,
                    name=f'{label} (FRED API)',
                    price=latest_value,
                    change=latest_value - previous_value,
                    change_percent=((latest_value - previous_value) / previous_value * 100) if previous_value else 0,
                    currency='PCT',
                    source='fred-api',
                    as_of=as_of,
                )
            )

        sections = self._empty_payload()
        sections['rates'] = rates
        return sections

    async def _fetch_fred_public_rates(self) -> dict[SectionName, list[MarketPoint]]:
        await self.fred_limiter.acquire()

        rates: list[MarketPoint] = []
        for series_id, symbol, label in FRED_SERIES:
            csv_payload = await self.http.get_text(
                'https://fred.stlouisfed.org/graph/fredgraph.csv',
                params={'id': series_id},
                timeout=self.settings.fred_public_timeout_seconds,
                retries=1,
            )

            reader = csv.DictReader(io.StringIO(csv_payload))
            values: list[float] = []
            last_date: str | None = None

            for row in reader:
                value = self._safe_float(row.get(series_id))
                if value is None:
                    continue
                values.append(value)
                last_date = row.get('DATE')

            if not values:
                continue

            latest_value = values[-1]
            previous_value = values[-2] if len(values) > 1 else latest_value
            as_of = self._parse_date_to_utc(last_date) or datetime.now(timezone.utc)

            rates.append(
                MarketPoint(
                    symbol=symbol,
                    name=f'{label} (FRED Public)',
                    price=latest_value,
                    change=latest_value - previous_value,
                    change_percent=((latest_value - previous_value) / previous_value * 100) if previous_value else 0,
                    currency='PCT',
                    source='fred-public',
                    as_of=as_of,
                )
            )

        sections = self._empty_payload()
        sections['rates'] = rates
        return sections

    async def _fetch_coingecko_crypto(self) -> dict[SectionName, list[MarketPoint]]:
        await self.coingecko_limiter.acquire()

        payload = await self.http.get_json(
            'https://api.coingecko.com/api/v3/simple/price',
            params={
                'ids': 'bitcoin,ethereum,solana',
                'vs_currencies': 'usd',
                'include_24hr_change': 'true',
            },
            timeout=self.settings.coingecko_timeout_seconds,
            retries=2,
        )

        mapping = {
            'bitcoin': ('BTC-USD', 'Bitcoin'),
            'ethereum': ('ETH-USD', 'Ethereum'),
            'solana': ('SOL-USD', 'Solana'),
        }

        as_of = datetime.now(timezone.utc)
        output: list[MarketPoint] = []
        for coin_id, (symbol, name) in mapping.items():
            item = payload.get(coin_id) if isinstance(payload, dict) else None
            if not isinstance(item, dict):
                continue

            price = self._safe_float(item.get('usd'))
            if price is None:
                continue

            change_percent = self._safe_float(item.get('usd_24h_change')) or 0
            change = price * (change_percent / 100)

            output.append(
                MarketPoint(
                    symbol=symbol,
                    name=name,
                    price=price,
                    change=change,
                    change_percent=change_percent,
                    currency='USD',
                    source='coingecko',
                    as_of=as_of,
                )
            )

        sections = self._empty_payload()
        sections['crypto'] = output
        return sections

    @staticmethod
    def _empty_payload() -> dict[SectionName, list[MarketPoint]]:
        return {
            'indices': [],
            'rates': [],
            'fx': [],
            'commodities': [],
            'crypto': [],
        }

    @staticmethod
    def _has_any_provider_payload(payload: dict[SectionName, list[MarketPoint]]) -> bool:
        return any(payload.values())

    @staticmethod
    def _merge_missing_target_points(
        existing: list[MarketPoint],
        incoming: list[MarketPoint],
        expected_symbols: set[str],
    ) -> int:
        known_symbols = {point.symbol for point in existing}
        added = 0

        for point in incoming:
            if point.symbol not in expected_symbols:
                continue
            if point.symbol in known_symbols:
                continue
            existing.append(point)
            known_symbols.add(point.symbol)
            added += 1

        return added

    @staticmethod
    def _order_section_points(section: SectionName, points: list[MarketPoint]) -> list[MarketPoint]:
        order = {symbol: idx for idx, (symbol, _, _) in enumerate(SECTION_TARGETS[section])}
        return sorted(points, key=lambda point: order.get(point.symbol, 9999))

    @staticmethod
    def _latest_as_of(points: list[MarketPoint]) -> datetime | None:
        timestamps = [point.as_of for point in points if point.as_of is not None]
        if not timestamps:
            return None
        return max(timestamps)

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value in (None, '', 'N/D', '.', 'null', 'None'):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

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
    def _parse_dt(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _parse_date_to_utc(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None

        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return None

        return datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc)

    @staticmethod
    def _summarize_error(exc: Exception) -> str:
        if isinstance(exc, HttpRequestError):
            if exc.status_code is not None:
                return f'HTTP {exc.status_code}'
            return str(exc)

        message = str(exc).strip()
        return message[:180] if message else exc.__class__.__name__

