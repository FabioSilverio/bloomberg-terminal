import asyncio
import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.core.container import get_container
from app.schemas.intraday import IntradayResponse
from app.schemas.market import MarketOverviewResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/market', tags=['market'])


@router.get('/overview', response_model=MarketOverviewResponse)
async def get_market_overview() -> MarketOverviewResponse:
    container = get_container()
    return await container.market_overview.get_overview()


@router.get('/intraday/{symbol}', response_model=IntradayResponse)
async def get_intraday(symbol: str) -> IntradayResponse:
    container = get_container()

    try:
        return await container.realtime_market.get_intraday(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def stream_market_overview(websocket: WebSocket) -> None:
    container = get_container()
    await websocket.accept()

    try:
        while True:
            payload = await container.market_overview.get_overview()
            await websocket.send_json(payload.model_dump(mode='json', by_alias=True))
            await asyncio.sleep(container.settings.market_ws_interval_seconds)
    except WebSocketDisconnect:
        logger.info('Market overview websocket disconnected')
    except Exception:
        logger.exception('Market overview websocket failed')
        await websocket.close(code=1011)


async def stream_intraday(websocket: WebSocket, symbol: str) -> None:
    container = get_container()
    await websocket.accept()

    try:
        while True:
            payload = await container.realtime_market.get_intraday(symbol)
            await websocket.send_json(payload.model_dump(mode='json', by_alias=True))
            await asyncio.sleep(container.settings.market_ws_interval_seconds)
    except ValueError as exc:
        await websocket.send_json({'error': str(exc)})
        await websocket.close(code=1008)
    except WebSocketDisconnect:
        logger.info('Intraday websocket disconnected symbol=%s', symbol)
    except Exception:
        logger.exception('Intraday websocket failed symbol=%s', symbol)
        await websocket.close(code=1011)


@router.websocket('/overview')
async def market_overview_ws(websocket: WebSocket) -> None:
    await stream_market_overview(websocket)


@router.websocket('/intraday/{symbol}')
async def market_intraday_ws(websocket: WebSocket, symbol: str) -> None:
    await stream_intraday(websocket, symbol)
