import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.container import get_container
from app.schemas.market import MarketOverviewResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/market', tags=['market'])


@router.get('/overview', response_model=MarketOverviewResponse)
async def get_market_overview() -> MarketOverviewResponse:
    container = get_container()
    return await container.market_overview.get_overview()


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


@router.websocket('/overview')
async def market_overview_ws(websocket: WebSocket) -> None:
    await stream_market_overview(websocket)
