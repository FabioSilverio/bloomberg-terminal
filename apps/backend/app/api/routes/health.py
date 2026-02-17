from fastapi import APIRouter

from app.core.container import get_container

router = APIRouter(prefix='/health', tags=['health'])


@router.get('')
async def health_check() -> dict[str, str]:
    return {'status': 'ok'}


@router.get('/providers')
async def provider_health() -> dict:
    container = get_container()
    return await container.market_overview.get_provider_status()
