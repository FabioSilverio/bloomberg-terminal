from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.market import router as market_router
from app.api.routes.watchlist import router as watchlist_router

api_router = APIRouter(prefix='/api/v1')
api_router.include_router(health_router)
api_router.include_router(market_router)
api_router.include_router(watchlist_router)
