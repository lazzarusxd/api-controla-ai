from typing import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.infra.database.postgres import PostgresPool
from app.infra.cache.redis_client import RedisClient
from app.infra.logging.setup import configure_logging
from app.config.settings import Settings, get_settings
from app.infra.cache import redis_client as redis_module
from app.infra.database import postgres as postgres_module
from app.presentation.health.router import router as health_router


logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()

    logger.info("application_starting", app=settings.APP_NAME, env=settings.APP_ENV)

    postgres_module.postgres_pool = PostgresPool(settings)
    await postgres_module.postgres_pool.connect()

    redis_module.redis_client = RedisClient(settings)
    await redis_module.redis_client.connect()

    logger.info("application_started")

    try:
        yield
    finally:
        logger.info("application_stopping")

        if redis_module.redis_client is not None:
            await redis_module.redis_client.disconnect()
            redis_module.redis_client = None

        if postgres_module.postgres_pool is not None:
            await postgres_module.postgres_pool.disconnect()
            postgres_module.postgres_pool = None

        logger.info("application_stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    configure_logging(settings)

    fastapi_app = FastAPI(
        title="Controla AI",
        description="API de gestão financeira e patrimonial com ingestão automatizada de comprovantes.",
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.APP_DEBUG,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json"
    )

    app.include_router(health_router)

    return fastapi_app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.APP_PORT,
        log_level=settings.LOG_LEVEL.lower()
    )
