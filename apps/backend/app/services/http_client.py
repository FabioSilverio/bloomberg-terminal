from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


class HttpRequestError(RuntimeError):
    def __init__(
        self,
        *,
        url: str,
        params: dict[str, Any] | None,
        attempts: int,
        status_code: int | None,
        detail: str | None,
        cause: Exception | None,
    ) -> None:
        self.url = url
        self.params = params
        self.attempts = attempts
        self.status_code = status_code
        self.detail = detail
        self.cause = cause

        status_text = f'HTTP {status_code}' if status_code is not None else 'request error'
        detail_text = f' ({detail})' if detail else ''
        super().__init__(f'{status_text} for {url} after {attempts} attempt(s){detail_text}')


class HttpClient:
    def __init__(self, *, default_headers: dict[str, str] | None = None) -> None:
        self._client = httpx.AsyncClient(
            headers=default_headers or {},
            follow_redirects=True,
        )

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
        retries: int = 2,
        retry_statuses: Iterable[int] | None = None,
        backoff_base_seconds: float = 0.35,
        backoff_cap_seconds: float = 4.0,
    ) -> Any:
        response = await self._request_with_retries(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            retries=retries,
            retry_statuses=retry_statuses,
            backoff_base_seconds=backoff_base_seconds,
            backoff_cap_seconds=backoff_cap_seconds,
        )

        try:
            return response.json()
        except ValueError as exc:
            detail = 'invalid JSON response'
            raise HttpRequestError(
                url=url,
                params=params,
                attempts=retries + 1,
                status_code=response.status_code,
                detail=detail,
                cause=exc,
            ) from exc

    async def get_text(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
        retries: int = 2,
        retry_statuses: Iterable[int] | None = None,
        backoff_base_seconds: float = 0.35,
        backoff_cap_seconds: float = 4.0,
    ) -> str:
        response = await self._request_with_retries(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            retries=retries,
            retry_statuses=retry_statuses,
            backoff_base_seconds=backoff_base_seconds,
            backoff_cap_seconds=backoff_cap_seconds,
        )
        return response.text

    async def _request_with_retries(
        self,
        url: str,
        *,
        params: dict[str, Any] | None,
        headers: dict[str, str] | None,
        timeout: float,
        retries: int,
        retry_statuses: Iterable[int] | None,
        backoff_base_seconds: float,
        backoff_cap_seconds: float,
    ) -> httpx.Response:
        retryable_statuses = set(retry_statuses or DEFAULT_RETRYABLE_STATUS_CODES)
        last_exception: Exception | None = None
        status_code: int | None = None
        detail: str | None = None

        for attempt in range(1, retries + 2):
            try:
                response = await self._client.get(url, params=params, headers=headers, timeout=timeout)
                status_code = response.status_code

                if status_code in retryable_statuses and attempt <= retries:
                    detail = self._extract_detail(response)
                    await self._sleep_before_retry(attempt, backoff_base_seconds, backoff_cap_seconds)
                    continue

                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                last_exception = exc
                status_code = exc.response.status_code
                detail = self._extract_detail(exc.response)
                if status_code in retryable_statuses and attempt <= retries:
                    await self._sleep_before_retry(attempt, backoff_base_seconds, backoff_cap_seconds)
                    continue
                break
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                last_exception = exc
                detail = str(exc)
                if attempt <= retries:
                    await self._sleep_before_retry(attempt, backoff_base_seconds, backoff_cap_seconds)
                    continue
                break

        logger.warning(
            'HTTP request failed url=%s params=%s status=%s attempts=%s detail=%s err=%s',
            url,
            params,
            status_code,
            retries + 1,
            detail,
            last_exception,
        )

        raise HttpRequestError(
            url=url,
            params=params,
            attempts=retries + 1,
            status_code=status_code,
            detail=detail,
            cause=last_exception,
        ) from last_exception

    @staticmethod
    async def _sleep_before_retry(attempt: int, base_seconds: float, cap_seconds: float) -> None:
        backoff_seconds = min(base_seconds * (2 ** (attempt - 1)), cap_seconds)
        await asyncio.sleep(backoff_seconds)

    @staticmethod
    def _extract_detail(response: httpx.Response) -> str | None:
        text = (response.text or '').strip()
        if not text:
            return None
        return text[:180]

    async def close(self) -> None:
        await self._client.aclose()
