from typing import Dict

import structlog
from fastapi import APIRouter, Response, status

from app.config.settings import get_settings
from app.infra.cache import redis_client as redis_module
from app.infra.database import postgres as postgres_module
from app.presentation.health.schemas import DependencyStatus, LivenessResponse, ReadinessResponse, StartupResponse


logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    path="/liveness",
    response_model=LivenessResponse,
    summary="Verifica se o processo está vivo"
)
async def liveness() -> LivenessResponse:
    settings = get_settings()
    return LivenessResponse(app=settings.APP_NAME)


@router.get(
    path="/startup",
    response_model=StartupResponse,
    summary="Verifica se a inicialização foi concluída"
)
async def startup(response: Response) -> StartupResponse:
    postgres_ready = (
        postgres_module.postgres_pool is not None
        and postgres_module.postgres_pool.is_connected
    )

    redis_ready = (
        redis_module.redis_client is not None
        and redis_module.redis_client.is_connected
    )

    dependencies: Dict[str, DependencyStatus] = {
        "redis": "up" if redis_ready else "down",
        "postgres": "up" if postgres_ready else "down"
    }

    if postgres_ready and redis_ready:
        return StartupResponse(status="started", dependencies=dependencies)

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return StartupResponse(status="starting", dependencies=dependencies)


@router.get(
    path="/readiness",
    response_model=ReadinessResponse,
    summary="Verifica se as dependências estão acessíveis"
)
async def readiness(response: Response) -> ReadinessResponse:
    redis_up = False
    postgres_up = False

    if (
        postgres_module.postgres_pool is not None
        and postgres_module.postgres_pool.is_connected
    ):
        postgres_up = await postgres_module.postgres_pool.ping()

    if (
        redis_module.redis_client is not None
        and redis_module.redis_client.is_connected
    ):
        redis_up = await redis_module.redis_client.ping()

    dependencies: Dict[str, DependencyStatus] = {
        "redis": "up" if redis_up else "down",
        "postgres": "up" if postgres_up else "down"
    }

    if postgres_up and redis_up:
        return ReadinessResponse(status="ready", dependencies=dependencies)

    logger.warning("readiness_check_failed", dependencies=dependencies)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="not_ready", dependencies=dependencies)
