from datetime import datetime
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, Field

AlertDirection = Literal['above', 'below']


class PriceAlertUpsertRequest(BaseModel):
    enabled: bool = True
    direction: AlertDirection = 'above'
    target_price: Optional[float] = Field(
        default=None,
        serialization_alias='targetPrice',
        validation_alias=AliasChoices('target_price', 'targetPrice'),
    )


class PriceAlertResponse(BaseModel):
    id: int
    watchlist_item_id: int = Field(
        serialization_alias='watchlistItemId',
        validation_alias=AliasChoices('watchlist_item_id', 'watchlistItemId'),
    )
    symbol: str
    enabled: bool
    direction: AlertDirection
    target_price: Optional[float] = Field(
        default=None,
        serialization_alias='targetPrice',
        validation_alias=AliasChoices('target_price', 'targetPrice'),
    )
    created_at: datetime = Field(
        serialization_alias='createdAt',
        validation_alias=AliasChoices('created_at', 'createdAt'),
    )
    updated_at: datetime = Field(
        serialization_alias='updatedAt',
        validation_alias=AliasChoices('updated_at', 'updatedAt'),
    )


class PriceAlertListResponse(BaseModel):
    items: list[PriceAlertResponse] = Field(default_factory=list)
