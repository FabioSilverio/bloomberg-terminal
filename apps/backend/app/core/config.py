from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'OpenBloom API'
    app_env: str = 'development'
    app_debug: bool = False

    cors_origins: list[str] = Field(default_factory=lambda: ['http://localhost:3000'])

    database_url: str = 'postgresql+asyncpg://postgres:postgres@postgres:5432/openbloom'
    redis_url: str = 'redis://redis:6379/0'

    market_cache_ttl_seconds: int = 20
    market_stale_ttl_seconds: int = 300
    market_ws_interval_seconds: int = 10

    yahoo_timeout_seconds: float = 8.0
    yahoo_max_retries: int = 2
    yahoo_rate_limit_per_minute: int = 40
    yahoo_user_agent: str = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
    )
    yahoo_accept_language: str = 'en-US,en;q=0.9'
    yahoo_endpoints: list[str] = Field(
        default_factory=lambda: [
            'https://query1.finance.yahoo.com/v7/finance/quote',
            'https://query2.finance.yahoo.com/v7/finance/quote',
        ]
    )

    stooq_timeout_seconds: float = 8.0
    stooq_rate_limit_per_minute: int = 30

    coingecko_timeout_seconds: float = 8.0
    coingecko_rate_limit_per_minute: int = 20

    fred_api_key: str | None = None
    fred_timeout_seconds: float = 8.0
    fred_public_timeout_seconds: float = 8.0
    fred_rate_limit_per_minute: int = 30

    alpha_vantage_api_key: str | None = None
    finnhub_api_key: str | None = None
    polygon_api_key: str | None = None
    news_api_key: str | None = None
    sec_user_agent: str = 'openbloom/0.1 (support@local)'


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
