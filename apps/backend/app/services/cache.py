from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    payload: Any
    expires_at: float


class InMemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            if item.expires_at < time.time():
                self._store.pop(key, None)
                return None
            return item.payload

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        async with self._lock:
            self._store[key] = CacheEntry(payload=value, expires_at=time.time() + ttl_seconds)


class CacheClient:
    def __init__(self, redis_url: str | None) -> None:
        self.redis: Redis | None = None
        self.memory = InMemoryCache()

        if redis_url:
            try:
                self.redis = Redis.from_url(redis_url, decode_responses=True)
            except Exception:  # pragma: no cover - defensive init fallback
                logger.exception('Failed to initialize Redis client, falling back to memory cache')
                self.redis = None

    async def get(self, key: str) -> Any | None:
        if self.redis:
            try:
                data = await self.redis.get(key)
                if data is not None:
                    return json.loads(data)
            except Exception:
                logger.exception('Redis read failed for key=%s. Falling back to memory cache.', key)

        return await self.memory.get(key)

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if self.redis:
            try:
                await self.redis.set(name=key, value=json.dumps(value), ex=ttl_seconds)
                return
            except Exception:
                logger.exception('Redis write failed for key=%s. Falling back to memory cache.', key)

        await self.memory.set(key, value, ttl_seconds)
