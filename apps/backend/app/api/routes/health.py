from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.container import get_container
from app.db.session import engine

router = APIRouter(prefix='/health', tags=['health'])

REQUIRED_TABLES = {'watchlist_items', 'price_alerts', 'alert_trigger_events'}


@router.get('')
async def health_check() -> dict:
    return {
        'status': 'ok',
        'service': get_container().settings.app_name,
        'asOf': datetime.now(timezone.utc).isoformat(),
    }


@router.get('/ready')
async def readiness_check() -> JSONResponse:
    details: dict[str, object] = {
        'status': 'ok',
        'database': 'ok',
        'migrations': 'ok',
        'missingTables': [],
        'alembicVersion': None,
        'asOf': datetime.now(timezone.utc).isoformat(),
    }

    status_code = 200

    try:
        async with engine.connect() as connection:
            await connection.execute(text('SELECT 1'))

            table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
            missing_tables = sorted(REQUIRED_TABLES - table_names)
            details['missingTables'] = missing_tables

            version_row = await connection.execute(text('SELECT version_num FROM alembic_version LIMIT 1'))
            details['alembicVersion'] = version_row.scalar_one_or_none()

            if missing_tables:
                details['status'] = 'degraded'
                details['migrations'] = 'missing_tables'
                status_code = 503

    except SQLAlchemyError as exc:
        details['status'] = 'error'
        details['database'] = 'error'
        details['migrations'] = 'unknown'
        details['error'] = f'{exc.__class__.__name__}: {exc}'
        status_code = 503

    return JSONResponse(status_code=status_code, content=details)


@router.get('/providers')
async def provider_health() -> dict:
    container = get_container()
    return await container.market_overview.get_provider_status()
