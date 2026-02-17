from functools import lru_cache

from app.core.config import get_settings
from app.services.cache import CacheClient
from app.services.http_client import HttpClient
from app.services.market_overview import MarketOverviewService
from app.services.price_alerts import PriceAlertService
from app.services.realtime_market import RealtimeMarketService
from app.services.watchlist import WatchlistService


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
        self.realtime_market = RealtimeMarketService(
            settings=self.settings,
            cache=self.cache,
            http_client=self.http_client,
        )
        self.price_alerts = PriceAlertService()
        self.watchlist = WatchlistService(
            settings=self.settings,
            realtime_market=self.realtime_market,
            price_alerts=self.price_alerts,
        )

    async def shutdown(self) -> None:
        await self.http_client.close()


@lru_cache(maxsize=1)
def get_container() -> ServiceContainer:
    return ServiceContainer()
