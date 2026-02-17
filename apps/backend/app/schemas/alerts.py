from datetime import datetime
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, Field, model_validator

AlertCondition = Literal[
    'price_above',
    'price_below',
    'crosses_above',
    'crosses_below',
    'percent_move_up',
    'percent_move_down',
]

AlertSource = Literal['manual', 'watchlist', 'command', 'system']
AlertStatus = Literal['active', 'inactive']
AlertTriggerState = Literal['armed', 'active', 'cooldown', 'triggered', 'inactive']
AlertDirection = Literal['above', 'below']


class PriceAlertUpsertRequest(BaseModel):
    enabled: bool = True
    direction: AlertDirection = 'above'
    target_price: Optional[float] = Field(
        default=None,
        serialization_alias='targetPrice',
        validation_alias=AliasChoices('target_price', 'targetPrice'),
    )
    one_shot: bool = Field(
        default=False,
        serialization_alias='oneShot',
        validation_alias=AliasChoices('one_shot', 'oneShot'),
    )
    cooldown_seconds: Optional[int] = Field(
        default=None,
        serialization_alias='cooldownSeconds',
        validation_alias=AliasChoices('cooldown_seconds', 'cooldownSeconds'),
    )


class PriceAlertCreateRequest(BaseModel):
    symbol: Optional[str] = None
    watchlist_item_id: Optional[int] = Field(
        default=None,
        serialization_alias='watchlistItemId',
        validation_alias=AliasChoices('watchlist_item_id', 'watchlistItemId'),
    )
    condition: AlertCondition
    threshold: float
    enabled: bool = True
    one_shot: bool = Field(
        default=False,
        serialization_alias='oneShot',
        validation_alias=AliasChoices('one_shot', 'oneShot'),
    )
    repeating: Optional[bool] = None
    cooldown_seconds: Optional[int] = Field(
        default=None,
        serialization_alias='cooldownSeconds',
        validation_alias=AliasChoices('cooldown_seconds', 'cooldownSeconds'),
    )
    source: Optional[AlertSource] = None

    @model_validator(mode='after')
    def validate_identity(self) -> 'PriceAlertCreateRequest':
        if not self.symbol and self.watchlist_item_id is None:
            raise ValueError('Either symbol or watchlistItemId is required')
        return self


class PriceAlertUpdateRequest(BaseModel):
    symbol: Optional[str] = None
    watchlist_item_id: Optional[int] = Field(
        default=None,
        serialization_alias='watchlistItemId',
        validation_alias=AliasChoices('watchlist_item_id', 'watchlistItemId'),
    )
    condition: Optional[AlertCondition] = None
    threshold: Optional[float] = None
    enabled: Optional[bool] = None
    one_shot: Optional[bool] = Field(
        default=None,
        serialization_alias='oneShot',
        validation_alias=AliasChoices('one_shot', 'oneShot'),
    )
    repeating: Optional[bool] = None
    cooldown_seconds: Optional[int] = Field(
        default=None,
        serialization_alias='cooldownSeconds',
        validation_alias=AliasChoices('cooldown_seconds', 'cooldownSeconds'),
    )
    source: Optional[AlertSource] = None


class PriceAlertResponse(BaseModel):
    id: int
    watchlist_item_id: Optional[int] = Field(
        default=None,
        serialization_alias='watchlistItemId',
        validation_alias=AliasChoices('watchlist_item_id', 'watchlistItemId'),
    )
    symbol: str
    instrument_type: Optional[str] = Field(
        default=None,
        serialization_alias='instrumentType',
        validation_alias=AliasChoices('instrument_type', 'instrumentType'),
    )
    source: str
    condition: AlertCondition
    threshold: float
    enabled: bool
    one_shot: bool = Field(
        serialization_alias='oneShot',
        validation_alias=AliasChoices('one_shot', 'oneShot'),
    )
    cooldown_seconds: int = Field(
        serialization_alias='cooldownSeconds',
        validation_alias=AliasChoices('cooldown_seconds', 'cooldownSeconds'),
    )
    trigger_state: AlertTriggerState = Field(
        serialization_alias='triggerState',
        validation_alias=AliasChoices('trigger_state', 'triggerState'),
    )
    active: bool
    in_cooldown: bool = Field(
        serialization_alias='inCooldown',
        validation_alias=AliasChoices('in_cooldown', 'inCooldown'),
    )
    last_condition_state: Optional[bool] = Field(
        default=None,
        serialization_alias='lastConditionState',
        validation_alias=AliasChoices('last_condition_state', 'lastConditionState'),
    )
    last_triggered_at: Optional[datetime] = Field(
        default=None,
        serialization_alias='lastTriggeredAt',
        validation_alias=AliasChoices('last_triggered_at', 'lastTriggeredAt'),
    )
    last_triggered_price: Optional[float] = Field(
        default=None,
        serialization_alias='lastTriggeredPrice',
        validation_alias=AliasChoices('last_triggered_price', 'lastTriggeredPrice'),
    )
    last_triggered_value: Optional[float] = Field(
        default=None,
        serialization_alias='lastTriggeredValue',
        validation_alias=AliasChoices('last_triggered_value', 'lastTriggeredValue'),
    )
    last_trigger_source: Optional[str] = Field(
        default=None,
        serialization_alias='lastTriggerSource',
        validation_alias=AliasChoices('last_trigger_source', 'lastTriggerSource'),
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


class AlertTriggerEventResponse(BaseModel):
    id: int
    alert_id: int = Field(
        serialization_alias='alertId',
        validation_alias=AliasChoices('alert_id', 'alertId'),
    )
    symbol: str
    condition: AlertCondition
    threshold: float
    trigger_price: float = Field(
        serialization_alias='triggerPrice',
        validation_alias=AliasChoices('trigger_price', 'triggerPrice'),
    )
    trigger_value: Optional[float] = Field(
        default=None,
        serialization_alias='triggerValue',
        validation_alias=AliasChoices('trigger_value', 'triggerValue'),
    )
    source: Optional[str] = None
    triggered_at: datetime = Field(
        serialization_alias='triggeredAt',
        validation_alias=AliasChoices('triggered_at', 'triggeredAt'),
    )


class AlertTriggerEventListResponse(BaseModel):
    items: list[AlertTriggerEventResponse] = Field(default_factory=list)
