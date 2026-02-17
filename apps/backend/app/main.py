from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.market import stream_intraday, stream_market_overview
from app.core.config import get_settings
from app.core.container import get_container
from app.core.logging import configure_logging

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_container()
    yield
    await get_container().shutdown()


app = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=lifespan)
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.websocket('/ws/market/overview')
async def market_overview_socket(websocket: WebSocket):
    await stream_market_overview(websocket)


@app.websocket('/ws/market/intraday/{symbol}')
async def market_intraday_socket(websocket: WebSocket, symbol: str):
    await stream_intraday(websocket, symbol)


@app.get('/')
async def root() -> dict[str, str]:
    return {'service': settings.app_name, 'status': 'running'}
