from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class HttpClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient()

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
        retries: int = 2,
    ) -> Any:
        last_exception: Exception | None = None

        for attempt in range(retries + 1):
            try:
                response = await self._client.get(url, params=params, headers=headers, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_exception = exc
                if attempt >= retries:
                    break
                backoff_seconds = 0.35 * (2**attempt)
                await asyncio.sleep(backoff_seconds)

        logger.warning('HTTP request failed url=%s params=%s err=%s', url, params, last_exception)
        raise RuntimeError(f'Failed request: {url}') from last_exception

    async def close(self) -> None:
        await self._client.aclose()
