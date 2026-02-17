from datetime import datetime, timezone
from pydantic import BaseModel, Field


class MarketPoint(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float = Field(serialization_alias='changePercent')
    currency: str | None = None
    source: str | None = None


class MarketSections(BaseModel):
    indices: list[MarketPoint] = Field(default_factory=list)
    rates: list[MarketPoint] = Field(default_factory=list)
    fx: list[MarketPoint] = Field(default_factory=list)
    commodities: list[MarketPoint] = Field(default_factory=list)
    crypto: list[MarketPoint] = Field(default_factory=list)


class MarketOverviewResponse(BaseModel):
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), serialization_alias='asOf')
    degraded: bool = False
    warnings: list[str] = Field(default_factory=list)
    sections: MarketSections
