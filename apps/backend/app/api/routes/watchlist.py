from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import get_container
from app.db.session import get_db
from app.schemas.watchlist import (
    WatchlistAddRequest,
    WatchlistItemResponse,
    WatchlistReorderRequest,
    WatchlistResponse,
)

router = APIRouter(prefix='/watchlist', tags=['watchlist'])


@router.get('', response_model=WatchlistResponse)
async def get_watchlist(db: AsyncSession = Depends(get_db)) -> WatchlistResponse:
    container = get_container()
    return await container.watchlist.get_snapshot(db)


@router.post('', response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
async def add_watchlist_item(payload: WatchlistAddRequest, db: AsyncSession = Depends(get_db)) -> WatchlistItemResponse:
    container = get_container()

    try:
        item, _ = await container.watchlist.add_symbol(db, payload.symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return WatchlistItemResponse(
        id=item.id,
        symbol=item.symbol,
        display_symbol=item.display_symbol,
        instrument_type=item.instrument_type,
        position=item.position,
        created_at=item.created_at,
        quote=None,
    )


@router.delete('/{item_id}', status_code=status.HTTP_204_NO_CONTENT)
async def remove_watchlist_item(item_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    container = get_container()
    removed = await container.watchlist.remove_item(db, item_id)
    if not removed:
        raise HTTPException(status_code=404, detail='Watchlist item not found')
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete('/by-symbol/{symbol}', status_code=status.HTTP_204_NO_CONTENT)
async def remove_watchlist_symbol(symbol: str, db: AsyncSession = Depends(get_db)) -> Response:
    container = get_container()

    try:
        removed = await container.watchlist.remove_symbol(db, symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not removed:
        raise HTTPException(status_code=404, detail='Symbol not present in watchlist')
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/reorder', response_model=list[WatchlistItemResponse])
async def reorder_watchlist(payload: WatchlistReorderRequest, db: AsyncSession = Depends(get_db)) -> list[WatchlistItemResponse]:
    container = get_container()
    items = await container.watchlist.reorder(db, payload.item_ids)

    return [
        WatchlistItemResponse(
            id=item.id,
            symbol=item.symbol,
            display_symbol=item.display_symbol,
            instrument_type=item.instrument_type,
            position=item.position,
            created_at=item.created_at,
            quote=None,
        )
        for item in items
    ]
