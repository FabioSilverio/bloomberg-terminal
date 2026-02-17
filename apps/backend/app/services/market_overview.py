from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from app.core.config import Settings
from app.schemas.market import MarketOverviewResponse, MarketPoint, MarketSections
from app.services.cache import CacheClient
from app.services.http_client import HttpClient
from app.services.rate_limiter import AsyncRateLimiter

logger = logging.getLogger(__name__)

SectionName = Literal['indices', 'rates', 'fx', 'commodities', 'crypto']

MMAP_SYMBOLS: list[tuple[SectionName, str, str]] = [
    ('indices', '^GSPC', 'S&P 500'),
    ('indices', '^DJI', 'Dow Jones Industrial Average'),
    ('indices', '^IXIC', 'Nasdaq Composite'),
    ('indices', '^RUT', 'Russell 2000'),
    ('rates', '^TNX', 'US 10Y Treasury Yield'),
    ('rates', '^FVX', 'US 5Y Treasury Yield'),
    ('rates', '^IRX', 'US 13W Treasury Yield'),
    ('fx', 'EURUSD=X', 'EUR/USD'),
    ('fx', 'USDJPY=X', 'USD/JPY'),
    ('fx', 'GBPUSD=X', 'GBP/USD'),
    ('commodities', 'CL=F', 'WTI Crude Oil'),
    ('commodities', 'GC=F', 'Gold'),
    ('commodities', 'SI=F', 'Silver'),
    ('commodities', 'HG=F', 'Copper'),
    ('crypto', 'BTC-USD', 'Bitcoin'),
    ('crypto', 'ETH-USD', 'Ethereum'),
    ('crypto', 'SOL-USD', 'Solana'),
]

FRED_SERIES: list[tuple[str, str]] = [
    ('DGS10', 'US 10Y Treasury (FRED)'),
    ('DGS2', 'US 2Y Treasury (FRED)'),
]


class MarketOverviewService:
    def __init__(self, settings: Settings, cache: CacheClient, http_client: HttpClient) -> None:
        self.settings = settings
        self.cache = cache
        self.http = http_client
        self.yahoo_limiter = AsyncRateLimiter(max_calls=settings.yahoo_rate_limit_per_minute, period_seconds=60)
        self.coingecko_limiter = AsyncRateLimiter(max_calls=settings.coingecko_rate_limit_per_minute, period_seconds=60)
        self.fred_limiter = AsyncRateLimiter(max_calls=settings.fred_rate_limit_per_minute, period_seconds=60)

    async def get_overview(self) -> MarketOverviewResponse:
        fresh_key = 'market:overview:fresh'
        stale_key = 'market:overview:stale'

        cached_fresh = await self.cache.get(fresh_key)
        if cached_fresh is not None:
            return MarketOverviewResponse.model_validate(cached_fresh)

        warnings: list[str] = []
        sections = MarketSections()

        try:
            yahoo_sections = await self._fetch_yahoo_sections()
            sections = self._merge_sections(sections, yahoo_sections)
        except Exception as exc:
            warnings.append(f'Yahoo Finance unavailable: {exc}')

        try:
            fred_rates = await self._fetch_fred_rates()
            sections.rates.extend(fred_rates)
        except Exception as exc:
            if self.settings.fred_api_key:
                warnings.append(f'FRED unavailable: {exc}')

        if not sections.crypto:
            try:
                sections.crypto = await self._fetch_coingecko_crypto()
                warnings.append('Using CoinGecko fallback for crypto quotes')
            except Exception as exc:
                warnings.append(f'CoinGecko unavailable: {exc}')

        if not any(
            [
                sections.indices,
                sections.rates,
                sections.fx,
                sections.commodities,
                sections.crypto,
            ]
        ):
            stale_payload = await self.cache.get(stale_key)
            if stale_payload is not None:
                stale_model = MarketOverviewResponse.model_validate(stale_payload)
                stale_warnings = list(stale_model.warnings)
                stale_warnings.extend(warnings)
                stale_warnings.append('Serving stale market cache due to provider failures')
                return stale_model.model_copy(update={'degraded': True, 'warnings': stale_warnings})

            raise RuntimeError('No market data sources available and no stale cache to serve')

        response = MarketOverviewResponse(
            as_of=datetime.now(timezone.utc),
            degraded=len(warnings) > 0,
            warnings=warnings,
            sections=sections,
        )

        serialized = response.model_dump(mode='json', by_alias=True)
        await self.cache.set(fresh_key, serialized, ttl_seconds=self.settings.market_cache_ttl_seconds)
        await self.cache.set(stale_key, serialized, ttl_seconds=self.settings.market_stale_ttl_seconds)

        return response

    async def _fetch_yahoo_sections(self) -> MarketSections:
        await self.yahoo_limiter.acquire()

        symbols = ','.join(symbol for _, symbol, _ in MMAP_SYMBOLS)
        payload = await self.http.get_json(
            'https://query1.finance.yahoo.com/v7/finance/quote',
            params={'symbols': symbols},
            timeout=self.settings.yahoo_timeout_seconds,
            retries=2,
        )

        by_symbol: dict[str, dict[str, Any]] = {
            str(item.get('symbol')): item for item in payload.get('quoteResponse', {}).get('result', [])
        }

        sections = MarketSections()

        for section, symbol, default_name in MMAP_SYMBOLS:
            row = by_symbol.get(symbol)
            if not row:
                continue

            point = MarketPoint(
                symbol=symbol,
                name=row.get('shortName') or row.get('longName') or default_name,
                price=float(row.get('regularMarketPrice') or 0),
                change=float(row.get('regularMarketChange') or 0),
                change_percent=float(row.get('regularMarketChangePercent') or 0),
                currency=row.get('currency'),
                source='yahoo',
            )

            getattr(sections, section).append(point)

        return sections

    async def _fetch_fred_rates(self) -> list[MarketPoint]:
        if not self.settings.fred_api_key:
            return []

        await self.fred_limiter.acquire()

        rates: list[MarketPoint] = []

        for series_id, label in FRED_SERIES:
            payload = await self.http.get_json(
                'https://api.stlouisfed.org/fred/series/observations',
                params={
                    'series_id': series_id,
                    'api_key': self.settings.fred_api_key,
                    'file_type': 'json',
                    'sort_order': 'desc',
                    'limit': 2,
                },
                timeout=self.settings.fred_timeout_seconds,
                retries=1,
            )

            observations = payload.get('observations', [])
            latest = next((item for item in observations if item.get('value') not in ('.', None)), None)
            previous = next(
                (item for item in observations[1:] if item.get('value') not in ('.', None)),
                None,
            )

            if latest is None:
                continue

            latest_value = float(latest['value'])
            prev_value = float(previous['value']) if previous else latest_value

            rates.append(
                MarketPoint(
                    symbol=series_id,
                    name=label,
                    price=latest_value,
                    change=latest_value - prev_value,
                    change_percent=((latest_value - prev_value) / prev_value * 100) if prev_value else 0,
                    currency='PCT',
                    source='fred',
                )
            )

        return rates

    async def _fetch_coingecko_crypto(self) -> list[MarketPoint]:
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

        output: list[MarketPoint] = []
        for coin_id, (symbol, name) in mapping.items():
            item = payload.get(coin_id)
            if not item:
                continue

            price = float(item.get('usd') or 0)
            change_percent = float(item.get('usd_24h_change') or 0)
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
                )
            )

        return output

    @staticmethod
    def _merge_sections(base: MarketSections, incoming: MarketSections) -> MarketSections:
        base.indices.extend(incoming.indices)
        base.rates.extend(incoming.rates)
        base.fx.extend(incoming.fx)
        base.commodities.extend(incoming.commodities)
        base.crypto.extend(incoming.crypto)
        return base
