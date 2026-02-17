from functools import lru_cache

from app.core.config import get_settings
from app.services.cache import CacheClient
from app.services.http_client import HttpClient
from app.services.market_overview import MarketOverviewService


class ServiceContainer:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.http_client = HttpClient()
        self.cache = CacheClient(self.settings.redis_url)
        self.market_overview = MarketOverviewService(
            settings=self.settings,
            cache=self.cache,
            http_client=self.http_client,
        )

    async def shutdown(self) -> None:
        await self.http_client.close()


@lru_cache(maxsize=1)
def get_container() -> ServiceContainer:
    return ServiceContainer()
