from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from app.core.config import Settings
from app.schemas.intraday import IntradayPoint, IntradayResponse
from app.services.cache import CacheClient
from app.services.http_client import HttpClient
from app.services.rate_limiter import AsyncRateLimiter

FIAT_CODES = {
    'USD',
    'EUR',
    'JPY',
    'GBP',
    'CHF',
    'CAD',
    'AUD',
    'NZD',
    'BRL',
    'CNY',
    'HKD',
    'SEK',
    'NOK',
    'MXN',
}

CRYPTO_CODES = {
    'BTC',
    'ETH',
    'SOL',
    'XRP',
    'DOGE',
    'BNB',
    'ADA',
    'AVAX',
    'DOT',
    'LTC',
}

INDEX_TO_STOOQ = {
    '^GSPC': '^spx',
    '^DJI': '^dji',
    '^IXIC': '^ndq',
    '^RUT': '^rut',
}


@dataclass(frozen=True)
class SymbolDescriptor:
    canonical: str
    provider_symbol: str
    display_symbol: str
    instrument_type: str


class RealtimeMarketService:
    def __init__(self, settings: Settings, cache: CacheClient, http_client: HttpClient) -> None:
        self.settings = settings
        self.cache = cache
        self.http = http_client
        self.yahoo_limiter = AsyncRateLimiter(max_calls=settings.intraday_rate_limit_per_minute, period_seconds=60)
        self.stooq_limiter = AsyncRateLimiter(max_calls=settings.stooq_rate_limit_per_minute, period_seconds=60)
        self._locks_guard = asyncio.Lock()
        self._symbol_locks: dict[str, asyncio.Lock] = {}

    def normalize_symbol(self, raw_symbol: str) -> SymbolDescriptor:
        raw = (raw_symbol or '').strip().upper().replace(' ', '')
        if not raw:
            raise ValueError('Symbol is required')

        if re.fullmatch(r'[A-Z]{3}[/-][A-Z]{3}', raw):
            base = raw[:3]
            quote_ccy = raw[-3:]
            canonical = f'{base}{quote_ccy}'
            return SymbolDescriptor(
                canonical=canonical,
                provider_symbol=f'{canonical}=X',
                display_symbol=f'{base}/{quote_ccy}',
                instrument_type='fx',
            )

        if re.fullmatch(r'[A-Z]{6}=X', raw):
            canonical = raw[:6]
            return SymbolDescriptor(
                canonical=canonical,
                provider_symbol=raw,
                display_symbol=f'{canonical[:3]}/{canonical[3:]}',
                instrument_type='fx',
            )

        if re.fullmatch(r'[A-Z]{6}', raw):
            base = raw[:3]
            quote_ccy = raw[3:]
            if base in CRYPTO_CODES and quote_ccy in {'USD', 'USDT'}:
                provider_symbol = f'{base}-{quote_ccy}'
                return SymbolDescriptor(
                    canonical=provider_symbol,
                    provider_symbol=provider_symbol,
                    display_symbol=f'{base}/{quote_ccy}',
                    instrument_type='crypto',
                )

            if base in FIAT_CODES and quote_ccy in FIAT_CODES:
                return SymbolDescriptor(
                    canonical=raw,
                    provider_symbol=f'{raw}=X',
                    display_symbol=f'{base}/{quote_ccy}',
                    instrument_type='fx',
                )

        if re.fullmatch(r'[A-Z]{2,6}-[A-Z]{3,4}', raw):
            base, quote_ccy = raw.split('-', 1)
            instrument_type = 'crypto' if base in CRYPTO_CODES else 'equity'
            return SymbolDescriptor(
                canonical=raw,
                provider_symbol=raw,
                display_symbol=f'{base}/{quote_ccy}',
                instrument_type=instrument_type,
            )

        if re.fullmatch(r'[\^A-Z][A-Z0-9.\-]{0,15}', raw):
            return SymbolDescriptor(
                canonical=raw,
                provider_symbol=raw,
                display_symbol=raw,
                instrument_type='equity',
            )

        raise ValueError(f'Unsupported symbol format: {raw_symbol}')

    async def get_intraday(self, raw_symbol: str) -> IntradayResponse:
        descriptor = self.normalize_symbol(raw_symbol)
        key_suffix = self._cache_key_suffix(descriptor.canonical)

        ui_key = f'market:intraday:{key_suffix}:ui'
        upstream_key = f'market:intraday:{key_suffix}:upstream'

        cached_ui = await self.cache.get(ui_key)
        if cached_ui is not None:
            return IntradayResponse.model_validate(cached_ui)

        symbol_lock = await self._get_symbol_lock(key_suffix)

        async with symbol_lock:
            cached_ui = await self.cache.get(ui_key)
            if cached_ui is not None:
                return IntradayResponse.model_validate(cached_ui)

            upstream_response, upstream_fetched_at = await self._load_upstream_snapshot(upstream_key)
            should_refresh_live = (
                upstream_response is None
                or upstream_fetched_at is None
                or (datetime.now(timezone.utc) - upstream_fetched_at).total_seconds()
                >= self.settings.market_upstream_refresh_seconds
            )

            response: IntradayResponse | None = upstream_response

            if should_refresh_live:
                live_response = await self._fetch_live_intraday(descriptor)
                if live_response is not None:
                    response = live_response
                    await self.cache.set(
                        upstream_key,
                        {
                            'fetchedAt': datetime.now(timezone.utc).isoformat(),
                            'payload': live_response.model_dump(mode='json', by_alias=True),
                        },
                        ttl_seconds=self.settings.market_stale_ttl_seconds,
                    )
                elif upstream_response is not None:
                    stale_warnings = self._dedupe(
                        [*upstream_response.warnings, 'Live refresh failed; serving stale snapshot.']
                    )
                    response = upstream_response.model_copy(
                        update={
                            'stale': True,
                            'warnings': stale_warnings,
                        }
                    )
                else:
                    response = self._empty_intraday_response(descriptor, warnings=['No live intraday data available.'])

            if response is None:
                response = self._empty_intraday_response(descriptor, warnings=['No intraday data available.'])

            freshness_seconds = int(max((datetime.now(timezone.utc) - response.as_of).total_seconds(), 0))
            response = response.model_copy(update={'freshness_seconds': freshness_seconds})

            await self.cache.set(
                ui_key,
                response.model_dump(mode='json', by_alias=True),
                ttl_seconds=self.settings.market_cache_ttl_seconds,
            )

            return response

    async def _load_upstream_snapshot(self, upstream_key: str) -> tuple[IntradayResponse | None, datetime | None]:
        upstream_payload = await self.cache.get(upstream_key)
        if not isinstance(upstream_payload, dict):
            return None, None

        upstream_response: IntradayResponse | None = None

        payload_raw = upstream_payload.get('payload')
        if payload_raw is not None:
            try:
                upstream_response = IntradayResponse.model_validate(payload_raw)
            except Exception:
                upstream_response = None

        upstream_fetched_at = self._parse_dt(upstream_payload.get('fetchedAt'))
        return upstream_response, upstream_fetched_at

    async def _get_symbol_lock(self, key_suffix: str) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._symbol_locks.get(key_suffix)
            if lock is None:
                lock = asyncio.Lock()
                self._symbol_locks[key_suffix] = lock
            return lock

    async def _fetch_live_intraday(self, descriptor: SymbolDescriptor) -> IntradayResponse | None:
        warnings: list[str] = []

        try:
            return await self._fetch_yahoo_intraday(descriptor)
        except Exception as exc:
            warnings.append(f'Yahoo chart unavailable ({self._summarize_error(exc)}).')

        try:
            fallback = await self._fetch_stooq_intraday(descriptor)
            if warnings:
                fallback = fallback.model_copy(update={'warnings': self._dedupe([*fallback.warnings, *warnings])})
            return fallback
        except Exception as exc:
            warnings.append(f'Stooq snapshot unavailable ({self._summarize_error(exc)}).')

        return None

    async def _fetch_yahoo_intraday(self, descriptor: SymbolDescriptor) -> IntradayResponse:
        await self.yahoo_limiter.acquire()

        encoded_symbol = quote(descriptor.provider_symbol, safe='^=.-')
        payload = await self.http.get_json(
            f'https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}',
            params={
                'interval': '5m',
                'range': '1d',
                'includePrePost': 'false',
                'events': 'div,splits',
            },
            timeout=self.settings.yahoo_timeout_seconds,
            retries=self.settings.yahoo_max_retries,
            headers={
                'Accept': 'application/json,text/plain,*/*',
                'Accept-Language': self.settings.yahoo_accept_language,
                'Origin': 'https://finance.yahoo.com',
                'Referer': 'https://finance.yahoo.com/',
                'User-Agent': self.settings.yahoo_user_agent,
            },
        )

        chart = payload.get('chart') if isinstance(payload, dict) else None
        if not isinstance(chart, dict):
            raise RuntimeError('Malformed Yahoo chart payload')

        if chart.get('error'):
            detail = chart['error'].get('description') if isinstance(chart['error'], dict) else 'unknown error'
            raise RuntimeError(str(detail))

        result = chart.get('result')
        if not isinstance(result, list) or not result:
            raise RuntimeError('Yahoo chart returned no result')

        first = result[0]
        if not isinstance(first, dict):
            raise RuntimeError('Yahoo chart result is invalid')

        meta = first.get('meta') if isinstance(first.get('meta'), dict) else {}
        timestamps = first.get('timestamp') if isinstance(first.get('timestamp'), list) else []
        indicators = first.get('indicators') if isinstance(first.get('indicators'), dict) else {}
        quote_list = indicators.get('quote') if isinstance(indicators.get('quote'), list) else []
        quote_data = quote_list[0] if quote_list and isinstance(quote_list[0], dict) else {}
        closes = quote_data.get('close') if isinstance(quote_data.get('close'), list) else []
        volumes = quote_data.get('volume') if isinstance(quote_data.get('volume'), list) else []

        points: list[IntradayPoint] = []
        for idx, ts in enumerate(timestamps):
            if not isinstance(ts, (int, float)):
                continue

            close_value = self._safe_float(closes[idx] if idx < len(closes) else None)
            if close_value is None:
                continue

            volume_value = self._safe_float(volumes[idx] if idx < len(volumes) else None)
            points.append(
                IntradayPoint(
                    time=datetime.fromtimestamp(float(ts), tz=timezone.utc),
                    price=close_value,
                    volume=volume_value,
                )
            )

        last_price = self._safe_float(meta.get('regularMarketPrice'))
        if last_price is None and points:
            last_price = points[-1].price

        previous_close = self._safe_float(meta.get('chartPreviousClose'))
        if previous_close is None:
            previous_close = self._safe_float(meta.get('previousClose'))
        if previous_close is None and points:
            previous_close = points[0].price

        if last_price is None:
            raise RuntimeError('Yahoo chart had no usable last price')

        market_time = self._safe_float(meta.get('regularMarketTime'))
        as_of = (
            datetime.fromtimestamp(market_time, tz=timezone.utc)
            if market_time is not None
            else (points[-1].time if points else datetime.now(timezone.utc))
        )

        volume = self._safe_float(meta.get('regularMarketVolume'))
        if volume is None and points and points[-1].volume is not None:
            volume = points[-1].volume

        if previous_close in (None, 0):
            change = 0.0
            change_percent = 0.0
        else:
            change = last_price - previous_close
            change_percent = (change / previous_close) * 100

        return IntradayResponse(
            symbol=descriptor.canonical,
            display_symbol=descriptor.display_symbol,
            instrument_type=descriptor.instrument_type,
            source='Yahoo Chart',
            as_of=as_of,
            last_price=last_price,
            change=change,
            change_percent=change_percent,
            volume=volume,
            currency=meta.get('currency') if isinstance(meta.get('currency'), str) else None,
            stale=False,
            warnings=[],
            points=points,
        )

    async def _fetch_stooq_intraday(self, descriptor: SymbolDescriptor) -> IntradayResponse:
        stooq_symbol = self._to_stooq_symbol(descriptor)
        if stooq_symbol is None:
            raise RuntimeError('No Stooq mapping available')

        await self.stooq_limiter.acquire()

        csv_payload = await self.http.get_text(
            f'https://stooq.com/q/l/?s={stooq_symbol}&f=sd2t2ohlcvn&e=csv',
            timeout=self.settings.stooq_timeout_seconds,
            retries=1,
            headers={
                'Accept': 'text/csv,*/*;q=0.8',
                'User-Agent': self.settings.yahoo_user_agent,
            },
        )

        rows = [line.strip() for line in csv_payload.splitlines() if line.strip()]
        if not rows:
            raise RuntimeError('Empty Stooq payload')

        row = rows[0].split(',')
        if row and row[0].strip().upper() == 'SYMBOL' and len(rows) > 1:
            row = rows[1].split(',')

        if len(row) < 7:
            raise RuntimeError('Unexpected Stooq row format')

        open_price = self._safe_float(row[3])
        close_price = self._safe_float(row[6])
        if close_price is None:
            raise RuntimeError('No close value from Stooq')

        date_raw = row[1].strip() if len(row) > 1 else ''
        time_raw = row[2].strip() if len(row) > 2 else '00:00:00'
        as_of = self._parse_stooq_datetime(date_raw, time_raw) or datetime.now(timezone.utc)

        previous = open_price if open_price not in (None, 0) else close_price
        change = close_price - previous
        change_percent = (change / previous * 100) if previous else 0.0

        points = [
            IntradayPoint(time=as_of - timedelta(minutes=5), price=previous, volume=self._safe_float(row[7]) if len(row) > 7 else None),
            IntradayPoint(time=as_of, price=close_price, volume=self._safe_float(row[7]) if len(row) > 7 else None),
        ]

        return IntradayResponse(
            symbol=descriptor.canonical,
            display_symbol=descriptor.display_symbol,
            instrument_type=descriptor.instrument_type,
            source='Stooq Snapshot',
            as_of=as_of,
            last_price=close_price,
            change=change,
            change_percent=change_percent,
            volume=self._safe_float(row[7]) if len(row) > 7 else None,
            currency='USD' if descriptor.instrument_type in {'equity', 'crypto'} else None,
            stale=True,
            warnings=['Near real-time snapshot from fallback source.'],
            points=points,
        )

    @staticmethod
    def _cache_key_suffix(symbol: str) -> str:
        return re.sub(r'[^A-Z0-9]+', '_', symbol.upper()).strip('_') or 'SYMBOL'

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value in (None, '', 'N/D', '.', 'null', 'None'):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

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
    def _parse_stooq_datetime(date_raw: str, time_raw: str) -> datetime | None:
        if not date_raw:
            return None

        candidate_formats = [
            f'{date_raw}T{time_raw}',
            f'{date_raw} {time_raw}',
            date_raw,
        ]

        for candidate in candidate_formats:
            try:
                parsed = datetime.fromisoformat(candidate)
            except ValueError:
                continue

            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)

        return None

    def _to_stooq_symbol(self, descriptor: SymbolDescriptor) -> str | None:
        canonical = descriptor.canonical

        if canonical in INDEX_TO_STOOQ:
            return INDEX_TO_STOOQ[canonical]

        if descriptor.instrument_type == 'fx':
            fx = canonical.replace('=X', '').replace('/', '').replace('-', '')
            if len(fx) == 6 and fx.isalpha():
                return fx.lower()
            return None

        if descriptor.instrument_type == 'equity':
            symbol = canonical.replace('^', '').replace('.', '-').lower()
            if not symbol:
                return None
            if '.us' in symbol:
                return symbol
            return f'{symbol}.us'

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
    def _summarize_error(exc: Exception) -> str:
        message = str(exc).strip()
        return message[:180] if message else exc.__class__.__name__

    @staticmethod
    def _empty_intraday_response(descriptor: SymbolDescriptor, *, warnings: list[str]) -> IntradayResponse:
        now = datetime.now(timezone.utc)
        return IntradayResponse(
            symbol=descriptor.canonical,
            display_symbol=descriptor.display_symbol,
            instrument_type=descriptor.instrument_type,
            source='Unavailable',
            as_of=now,
            last_price=0,
            change=0,
            change_percent=0,
            volume=None,
            currency=None,
            stale=True,
            warnings=warnings,
            points=[],
        )

