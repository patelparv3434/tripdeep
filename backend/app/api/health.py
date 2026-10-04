import logging

from fastapi import APIRouter
from psycopg import Error as PsycopgError
from pymongo.errors import PyMongoError

from app.agents.registry import AGENTS
from app.core.config import get_settings
from app.db.session import ping_database

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, object]:
    settings = get_settings()
    database_status = "in-memory" if settings.database_backend == "memory" else "connected"
    try:
        await ping_database()
    except (PsycopgError, PyMongoError):
        database_status = "unavailable"
        logger.exception("Health check database connection failed")

    agent_status = "available" if AGENTS else "unavailable"
    overall = (
        "healthy"
        if database_status == "connected" and agent_status == "available"
        else "degraded"
    )
    return {
        "status": overall,
        "database_engine": settings.database_backend,
        "database": database_status,
        "agents": agent_status,
        "agent_count": len(AGENTS),
    }