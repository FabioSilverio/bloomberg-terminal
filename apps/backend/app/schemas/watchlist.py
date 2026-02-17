from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, Field


class WatchlistAlert(BaseModel):
    id: int
    enabled: bool
    source: str
    condition: str
    threshold: float
    one_shot: bool = Field(
        serialization_alias='oneShot',
        validation_alias=AliasChoices('one_shot', 'oneShot'),
    )
    cooldown_seconds: int = Field(
        serialization_alias='cooldownSeconds',
        validation_alias=AliasChoices('cooldown_seconds', 'cooldownSeconds'),
    )
    trigger_state: Literal['armed', 'active', 'cooldown', 'triggered', 'inactive'] = Field(
        serialization_alias='triggerState',
        validation_alias=AliasChoices('trigger_state', 'triggerState'),
    )
    active: bool
    in_cooldown: bool = Field(
        serialization_alias='inCooldown',
        validation_alias=AliasChoices('in_cooldown', 'inCooldown'),
    )
    last_triggered_at: Optional[datetime] = Field(
        default=None,
        serialization_alias='lastTriggeredAt',
        validation_alias=AliasChoices('last_triggered_at', 'lastTriggeredAt'),
    )
    last_trigger_source: Optional[str] = Field(
        default=None,
        serialization_alias='lastTriggerSource',
        validation_alias=AliasChoices('last_trigger_source', 'lastTriggerSource'),
    )
    updated_at: datetime = Field(
        serialization_alias='updatedAt',
        validation_alias=AliasChoices('updated_at', 'updatedAt'),
    )


class WatchlistQuote(BaseModel):
    source: str
    as_of: datetime = Field(
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


class WatchlistItemResponse(BaseModel):
    id: int
    symbol: str
    display_symbol: str = Field(
        serialization_alias='displaySymbol',
        validation_alias=AliasChoices('display_symbol', 'displaySymbol'),
    )
    instrument_type: str = Field(
        serialization_alias='instrumentType',
        validation_alias=AliasChoices('instrument_type', 'instrumentType'),
    )
    position: int
    created_at: datetime = Field(
        serialization_alias='createdAt',
        validation_alias=AliasChoices('created_at', 'createdAt'),
    )
    quote: WatchlistQuote | None = None
    alerts: list[WatchlistAlert] = Field(default_factory=list)


class WatchlistResponse(BaseModel):
    as_of: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        serialization_alias='asOf',
        validation_alias=AliasChoices('as_of', 'asOf'),
    )
    items: list[WatchlistItemResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WatchlistAddRequest(BaseModel):
    symbol: str


class WatchlistReorderRequest(BaseModel):
    item_ids: list[int] = Field(
        default_factory=list,
        serialization_alias='itemIds',
        validation_alias=AliasChoices('item_ids', 'itemIds'),
    )
