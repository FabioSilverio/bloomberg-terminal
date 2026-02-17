from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import get_container
from app.db.session import get_db
from app.schemas.alerts import PriceAlertListResponse, PriceAlertResponse, PriceAlertUpsertRequest

router = APIRouter(prefix='/alerts', tags=['alerts'])


@router.get('', response_model=PriceAlertListResponse)
async def list_alerts(db: AsyncSession = Depends(get_db)) -> PriceAlertListResponse:
    container = get_container()
    alerts = await container.price_alerts.list_alerts(db)
    return PriceAlertListResponse(
        items=[
            PriceAlertResponse(
                id=alert.id,
                watchlist_item_id=alert.watchlist_item_id,
                symbol=alert.symbol,
                enabled=alert.enabled,
                direction=alert.direction,
                target_price=alert.target_price,
                created_at=alert.created_at,
                updated_at=alert.updated_at,
            )
            for alert in alerts
        ]
    )


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

    return PriceAlertResponse(
        id=alert.id,
        watchlist_item_id=alert.watchlist_item_id,
        symbol=alert.symbol,
        enabled=alert.enabled,
        direction=alert.direction,
        target_price=alert.target_price,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


@router.delete('/watchlist/{item_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_alert(item_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    container = get_container()
    removed = await container.price_alerts.delete_for_watchlist_item(db, item_id)
    if not removed:
        raise HTTPException(status_code=404, detail='Alert not found for watchlist item')
    return Response(status_code=status.HTTP_204_NO_CONTENT)
