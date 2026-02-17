from datetime import datetime, timezone

from pydantic import AliasChoices, BaseModel, Field


class MarketPoint(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float = Field(
        serialization_alias='changePercent',
        validation_alias=AliasChoices('change_percent', 'changePercent'),
    )
    currency: str | None = None
    source: str | None = None
    as_of: datetime | None = Field(
        default=None,
        serialization_alias='asOf',
        validation_alias=AliasChoices('as_of', 'asOf'),
    )


class MarketSections(BaseModel):
    indices: list[MarketPoint] = Field(default_factory=list)
    rates: list[MarketPoint] = Field(default_factory=list)
    fx: list[MarketPoint] = Field(default_factory=list)
    commodities: list[MarketPoint] = Field(default_factory=list)
    crypto: list[MarketPoint] = Field(default_factory=list)


class MarketSectionMeta(BaseModel):
    source: str | None = None
    sources: list[str] = Field(default_factory=list)
    as_of: datetime | None = Field(
        default=None,
        serialization_alias='asOf',
        validation_alias=AliasChoices('as_of', 'asOf'),
    )
    loaded: int = 0
    expected: int = 0
    stale: bool = False


class MarketOverviewResponse(BaseModel):
    as_of: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        serialization_alias='asOf',
        validation_alias=AliasChoices('as_of', 'asOf'),
    )
    degraded: bool = False
    banner: str | None = None
    warnings: list[str] = Field(default_factory=list)
    sections: MarketSections
    section_meta: dict[str, MarketSectionMeta] = Field(
        default_factory=dict,
        serialization_alias='sectionMeta',
        validation_alias=AliasChoices('section_meta', 'sectionMeta'),
    )
