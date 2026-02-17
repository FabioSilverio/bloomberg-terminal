from __future__ import annotations

import asyncio
import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from app.core.config import Settings
from app.schemas.market import MarketOverviewResponse, MarketPoint, MarketSections
from app.services.cache import CacheClient
from app.services.http_client import HttpClient, HttpRequestError
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

# Stooq fallback symbols (free, no API key).
STOOQ_SYMBOLS: list[tuple[SectionName, str, str, str, str | None]] = [
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

FRED_API_SERIES: list[tuple[str, str]] = [
    ('DGS10', 'US 10Y Treasury (FRED API)'),
    ('DGS2', 'US 2Y Treasury (FRED API)'),
]

FRED_PUBLIC_SERIES: list[tuple[str, str, str]] = [
    ('DGS10', '^TNX', 'US 10Y Treasury Yield (FRED Public)'),
    ('DGS5', '^FVX', 'US 5Y Treasury Yield (FRED Public)'),
    ('DGS3MO', '^IRX', 'US 13W Treasury Yield (FRED Public)'),
]

EXPECTED_SECTION_COUNTS: dict[SectionName, int] = {
    'indices': 4,
    'rates': 3,
    'fx': 3,
    'commodities': 4,
    'crypto': 3,
}


class MarketOverviewService:
    def __init__(self, settings: Settings, cache: CacheClient, http_client: HttpClient) -> None:
        self.settings = settings
        self.cache = cache
        self.http = http_client
        self.yahoo_limiter = AsyncRateLimiter(max_calls=settings.yahoo_rate_limit_per_minute, period_seconds=60)
        self.stooq_limiter = AsyncRateLimiter(max_calls=settings.stooq_rate_limit_per_minute, period_seconds=60)
        self.coingecko_limiter = AsyncRateLimiter(max_calls=settings.coingecko_rate_limit_per_minute, period_seconds=60)
        self.fred_limiter = AsyncRateLimiter(max_calls=settings.fred_rate_limit_per_minute, period_seconds=60)

        self._provider_lock = asyncio.Lock()
        self._provider_status: dict[str, dict[str, Any]] = {
            'yahoo': self._new_provider_state(),
            'stooq': self._new_provider_state(),
            'fred_api': self._new_provider_state(status='disabled' if not settings.fred_api_key else 'unknown'),
            'fred_public': self._new_provider_state(),
            'coingecko': self._new_provider_state(),
        }

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
            await self._record_provider_result('yahoo', success=True)
        except Exception as exc:
            await self._record_provider_result('yahoo', success=False, error=self._summarize_error(exc))
            warnings.append(f'Yahoo Finance unavailable ({self._summarize_error(exc)}).')

        if self._needs_stooq_fallback(sections):
            try:
                stooq_sections = await self._fetch_stooq_sections()
                added = self._merge_sections_missing(
                    sections,
                    stooq_sections,
                    section_names=('indices', 'fx', 'commodities'),
                )
                await self._record_provider_result('stooq', success=True)
                if added > 0:
                    warnings.append('Using Stooq fallback for indices, FX, and commodities.')
            except Exception as exc:
                await self._record_provider_result('stooq', success=False, error=self._summarize_error(exc))
                warnings.append(f'Stooq fallback unavailable ({self._summarize_error(exc)}).')

        if self.settings.fred_api_key:
            try:
                fred_rates = await self._fetch_fred_rates()
                sections.rates.extend(fred_rates)
                await self._record_provider_result('fred_api', success=True)
            except Exception as exc:
                await self._record_provider_result('fred_api', success=False, error=self._summarize_error(exc))
                warnings.append(f'FRED API unavailable ({self._summarize_error(exc)}).')

        if len(sections.rates) < EXPECTED_SECTION_COUNTS['rates']:
            try:
                public_rates = await self._fetch_fred_public_rates()
                added = self._merge_missing_points(sections.rates, public_rates)
                await self._record_provider_result('fred_public', success=True)
                if added > 0:
                    warnings.append('Using FRED public fallback for treasury rates.')
            except Exception as exc:
                await self._record_provider_result('fred_public', success=False, error=self._summarize_error(exc))
                warnings.append(f'FRED public fallback unavailable ({self._summarize_error(exc)}).')

        if not sections.crypto:
            try:
                sections.crypto = await self._fetch_coingecko_crypto()
                await self._record_provider_result('coingecko', success=True)
                if sections.crypto:
                    warnings.append('Using CoinGecko fallback for crypto quotes.')
            except Exception as exc:
                await self._record_provider_result('coingecko', success=False, error=self._summarize_error(exc))
                warnings.append(f'CoinGecko unavailable ({self._summarize_error(exc)}).')

        if warnings and any('Yahoo Finance unavailable' in warning for warning in warnings):
            warnings.append(
                'Tip: Yahoo may be rate-limiting requests. Increase MARKET_CACHE_TTL_SECONDS or MARKET_WS_INTERVAL_SECONDS to reduce request volume.'
            )

        warnings = self._dedupe(warnings)

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
                stale_warnings.append('Serving stale market cache due to provider failures.')
                return stale_model.model_copy(update={'degraded': True, 'warnings': self._dedupe(stale_warnings)})

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

    async def get_provider_status(self) -> dict[str, Any]:
        async with self._provider_lock:
            providers = {name: dict(state) for name, state in self._provider_status.items()}

        overall = 'ok'
        if any(state.get('status') == 'degraded' for state in providers.values()):
            overall = 'degraded'

        return {
            'as_of': datetime.now(timezone.utc).isoformat(),
            'status': overall,
            'providers': providers,
        }

    async def _fetch_yahoo_sections(self) -> MarketSections:
        symbols = ','.join(symbol for _, symbol, _ in MMAP_SYMBOLS)
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
            if self._has_any_data(sections):
                return sections

            errors.append(f'{endpoint}: empty quote payload')

        error_summary = '; '.join(errors) if errors else 'no Yahoo endpoint returned data'
        raise RuntimeError(error_summary)

    def _parse_yahoo_payload(self, payload: dict[str, Any]) -> MarketSections:
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

        sections = MarketSections()

        for section, symbol, default_name in MMAP_SYMBOLS:
            row = by_symbol.get(symbol.upper())
            if not row:
                continue

            price = self._safe_float(row.get('regularMarketPrice'))
            if price is None:
                continue

            change = self._safe_float(row.get('regularMarketChange')) or 0.0
            change_percent = self._safe_float(row.get('regularMarketChangePercent')) or 0.0

            point = MarketPoint(
                symbol=symbol,
                name=row.get('shortName') or row.get('longName') or default_name,
                price=price,
                change=change,
                change_percent=change_percent,
                currency=row.get('currency'),
                source='yahoo',
            )

            getattr(sections, section).append(point)

        return sections

    async def _fetch_stooq_sections(self) -> MarketSections:
        await self.stooq_limiter.acquire()

        symbols = '+'.join(symbol for _, symbol, _, _, _ in STOOQ_SYMBOLS)
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
            if key:
                by_symbol[key] = row

        sections = MarketSections()

        for section, stooq_symbol, output_symbol, default_name, currency in STOOQ_SYMBOLS:
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

            point = MarketPoint(
                symbol=output_symbol,
                name=label,
                price=close_price,
                change=change,
                change_percent=change_percent,
                currency=currency,
                source='stooq',
            )

            getattr(sections, section).append(point)

        if not self._has_any_data(sections):
            raise RuntimeError('Stooq returned no usable market rows')

        return sections

    async def _fetch_fred_rates(self) -> list[MarketPoint]:
        if not self.settings.fred_api_key:
            return []

        await self.fred_limiter.acquire()

        rates: list[MarketPoint] = []

        for series_id, label in FRED_API_SERIES:
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

            observations = payload.get('observations', [])
            latest = next((item for item in observations if self._safe_float(item.get('value')) is not None), None)
            previous = next(
                (item for item in observations[1:] if self._safe_float(item.get('value')) is not None),
                None,
            )

            if latest is None:
                continue

            latest_value = self._safe_float(latest.get('value'))
            prev_value = self._safe_float(previous.get('value')) if previous else latest_value
            if latest_value is None:
                continue

            prev_value = prev_value if prev_value is not None else latest_value

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

    async def _fetch_fred_public_rates(self) -> list[MarketPoint]:
        await self.fred_limiter.acquire()

        rates: list[MarketPoint] = []

        for series_id, symbol, label in FRED_PUBLIC_SERIES:
            csv_payload = await self.http.get_text(
                'https://fred.stlouisfed.org/graph/fredgraph.csv',
                params={'id': series_id},
                timeout=self.settings.fred_public_timeout_seconds,
                retries=1,
            )

            reader = csv.DictReader(io.StringIO(csv_payload))
            values: list[float] = []
            for row in reader:
                value = self._safe_float(row.get(series_id))
                if value is not None:
                    values.append(value)

            if not values:
                continue

            latest_value = values[-1]
            previous_value = values[-2] if len(values) > 1 else latest_value

            rates.append(
                MarketPoint(
                    symbol=symbol,
                    name=label,
                    price=latest_value,
                    change=latest_value - previous_value,
                    change_percent=((latest_value - previous_value) / previous_value * 100) if previous_value else 0,
                    currency='PCT',
                    source='fred-public',
                )
            )

        if not rates:
            raise RuntimeError('FRED public returned no usable rates')

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
                )
            )

        if not output:
            raise RuntimeError('CoinGecko returned no usable quotes')

        return output

    async def _record_provider_result(self, provider: str, *, success: bool, error: str | None = None) -> None:
        async with self._provider_lock:
            state = self._provider_status.setdefault(provider, self._new_provider_state())
            now = datetime.now(timezone.utc).isoformat()
            state['last_attempt_at'] = now

            if success:
                state['status'] = 'ok'
                state['last_success_at'] = now
                state['last_error'] = None
                state['success_count'] = int(state.get('success_count', 0)) + 1
                return

            if state.get('status') != 'disabled':
                state['status'] = 'degraded'
            state['failure_count'] = int(state.get('failure_count', 0)) + 1
            state['last_error'] = error or 'unknown error'

    @staticmethod
    def _new_provider_state(status: str = 'unknown') -> dict[str, Any]:
        return {
            'status': status,
            'last_attempt_at': None,
            'last_success_at': None,
            'last_error': None,
            'success_count': 0,
            'failure_count': 0,
        }

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value in (None, '', 'N/D', '.', 'null', 'None'):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _merge_sections(base: MarketSections, incoming: MarketSections) -> MarketSections:
        base.indices.extend(incoming.indices)
        base.rates.extend(incoming.rates)
        base.fx.extend(incoming.fx)
        base.commodities.extend(incoming.commodities)
        base.crypto.extend(incoming.crypto)
        return base

    @classmethod
    def _merge_sections_missing(
        cls,
        base: MarketSections,
        incoming: MarketSections,
        *,
        section_names: tuple[SectionName, ...],
    ) -> int:
        added = 0
        for section in section_names:
            added += cls._merge_missing_points(getattr(base, section), getattr(incoming, section))
        return added

    @staticmethod
    def _merge_missing_points(existing: list[MarketPoint], incoming: list[MarketPoint]) -> int:
        known_symbols = {point.symbol for point in existing}
        added = 0

        for point in incoming:
            if point.symbol in known_symbols:
                continue
            existing.append(point)
            known_symbols.add(point.symbol)
            added += 1

        return added

    @staticmethod
    def _needs_stooq_fallback(sections: MarketSections) -> bool:
        return (
            len(sections.indices) < EXPECTED_SECTION_COUNTS['indices']
            or len(sections.fx) < EXPECTED_SECTION_COUNTS['fx']
            or len(sections.commodities) < EXPECTED_SECTION_COUNTS['commodities']
        )

    @staticmethod
    def _has_any_data(sections: MarketSections) -> bool:
        return any([sections.indices, sections.rates, sections.fx, sections.commodities, sections.crypto])

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
    def _summarize_error(exc: Exception) -> str:
        if isinstance(exc, HttpRequestError):
            if exc.status_code is not None:
                return f'HTTP {exc.status_code}'
            return str(exc)

        message = str(exc).strip()
        return message[:180] if message else exc.__class__.__name__
