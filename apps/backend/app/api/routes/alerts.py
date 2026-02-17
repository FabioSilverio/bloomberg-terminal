from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import get_container
from app.db.session import get_db
from app.models.price_alert import AlertTriggerEvent, PriceAlert
from app.schemas.alerts import (
    AlertStatus,
    AlertTriggerEventListResponse,
    AlertTriggerEventResponse,
    PriceAlertCreateRequest,
    PriceAlertListResponse,
    PriceAlertResponse,
    PriceAlertUpdateRequest,
    PriceAlertUpsertRequest,
)

router = APIRouter(prefix='/alerts', tags=['alerts'])


def _serialize_alert(alert: PriceAlert, *, now: datetime | None = None) -> PriceAlertResponse:
    container = get_container()
    trigger_state, active, in_cooldown = container.price_alerts.compute_trigger_state(
        alert,
        now=now or datetime.now(timezone.utc),
    )

    return PriceAlertResponse(
        id=alert.id,
        watchlist_item_id=alert.watchlist_item_id,
        symbol=alert.symbol,
        instrument_type=alert.instrument_type,
        source=alert.source,
        condition=alert.condition,
        threshold=alert.threshold,
        enabled=alert.enabled,
        one_shot=alert.one_shot,
        cooldown_seconds=alert.cooldown_seconds,
        trigger_state=trigger_state,
        active=active,
        in_cooldown=in_cooldown,
        last_condition_state=alert.last_condition_state,
        last_triggered_at=alert.last_triggered_at,
        last_triggered_price=alert.last_triggered_price,
        last_triggered_value=alert.last_triggered_value,
        last_trigger_source=alert.last_trigger_source,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


def _serialize_event(event: AlertTriggerEvent) -> AlertTriggerEventResponse:
    return AlertTriggerEventResponse(
        id=event.id,
        alert_id=event.alert_id,
        symbol=event.symbol,
        condition=event.condition,
        threshold=event.threshold,
        trigger_price=event.trigger_price,
        trigger_value=event.trigger_value,
        source=event.source,
        triggered_at=event.triggered_at,
    )


@router.get('', response_model=PriceAlertListResponse)
async def list_alerts(
    symbol: str | None = None,
    enabled: bool | None = None,
    status_filter: AlertStatus | None = Query(default=None, alias='status'),
    db: AsyncSession = Depends(get_db),
) -> PriceAlertListResponse:
    container = get_container()
    alerts = await container.price_alerts.list_alerts(
        db,
        symbol=symbol,
        enabled=enabled,
        status=status_filter,
    )
    now = datetime.now(timezone.utc)
    return PriceAlertListResponse(items=[_serialize_alert(alert, now=now) for alert in alerts])


@router.post('', response_model=PriceAlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(payload: PriceAlertCreateRequest, db: AsyncSession = Depends(get_db)) -> PriceAlertResponse:
    container = get_container()

    try:
        alert = await container.price_alerts.create_alert(db, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _serialize_alert(alert)


@router.get('/events', response_model=AlertTriggerEventListResponse)
async def list_alert_events(
    symbol: str | None = None,
    alert_id: int | None = Query(default=None, alias='alertId'),
    after_id: int | None = Query(default=None, alias='afterId'),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> AlertTriggerEventListResponse:
    container = get_container()
    events = await container.price_alerts.list_events(
        db,
        symbol=symbol,
        alert_id=alert_id,
        after_id=after_id,
        limit=limit,
    )
    return AlertTriggerEventListResponse(items=[_serialize_event(event) for event in events])


@router.get('/{alert_id}', response_model=PriceAlertResponse)
async def get_alert(alert_id: int, db: AsyncSession = Depends(get_db)) -> PriceAlertResponse:
    container = get_container()
    alert = await container.price_alerts.get_alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail='Alert not found')
    return _serialize_alert(alert)


@router.patch('/{alert_id}', response_model=PriceAlertResponse)
async def patch_alert(
    alert_id: int,
    payload: PriceAlertUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> PriceAlertResponse:
    container = get_container()

    try:
        alert = await container.price_alerts.update_alert(db, alert_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _serialize_alert(alert)


@router.delete('/{alert_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(alert_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    container = get_container()
    removed = await container.price_alerts.delete_alert(db, alert_id)
    if not removed:
        raise HTTPException(status_code=404, detail='Alert not found')
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put('/watchlist/{item_id}', response_model=PriceAlertResponse)
async def upsert_watchlist_alert(
    item_id: int,
    payload: PriceAlertUpsertRequest,
    db: AsyncSession = Depends(get_db),
) -> PriceAlertResponse:
    container = get_container()

    try:
        alert = await container.price_alerts.upsert_for_watchlist_item(db, item_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _serialize_alert(alert)


@router.delete('/watchlist/{item_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_alert(item_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    container = get_container()
    removed = await container.price_alerts.delete_for_watchlist_item(db, item_id)
    if not removed:
        raise HTTPException(status_code=404, detail='Alert not found for watchlist item')
    return Response(status_code=status.HTTP_204_NO_CONTENT)
