from datetime import datetime, timezone

from pydantic import AliasChoices, BaseModel, Field


class IntradayPoint(BaseModel):
    time: datetime
    price: float
    volume: float | None = None


class IntradayResponse(BaseModel):
    symbol: str
    display_symbol: str = Field(
        serialization_alias='displaySymbol',
        validation_alias=AliasChoices('display_symbol', 'displaySymbol'),
    )
    instrument_type: str = Field(
        serialization_alias='instrumentType',
        validation_alias=AliasChoices('instrument_type', 'instrumentType'),
    )
    source: str
    as_of: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        serialization_alias='asOf',
        validation_alias=AliasChoices('as_of', 'asOf'),
    )
    last_price: float = Field(
        serialization_alias='lastPrice',
        validation_alias=AliasChoices('last_price', 'lastPrice'),
    )
    change: float
    change_percent: float = Field(
        serialization_alias='changePercent',
        validation_alias=AliasChoices('change_percent', 'changePercent'),
    )
    volume: float | None = None
    currency: str | None = None
    stale: bool = False
    freshness_seconds: int | None = Field(
        default=None,
        serialization_alias='freshnessSeconds',
        validation_alias=AliasChoices('freshness_seconds', 'freshnessSeconds'),
    )
    source_refresh_interval_seconds: int | None = Field(
        default=None,
        serialization_alias='sourceRefreshIntervalSeconds',
        validation_alias=AliasChoices('source_refresh_interval_seconds', 'sourceRefreshIntervalSeconds'),
    )
    upstream_refresh_interval_seconds: int | None = Field(
        default=None,
        serialization_alias='upstreamRefreshIntervalSeconds',
        validation_alias=AliasChoices('upstream_refresh_interval_seconds', 'upstreamRefreshIntervalSeconds'),
    )
    warnings: list[str] = Field(default_factory=list)
    points: list[IntradayPoint] = Field(default_factory=list)
