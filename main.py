from typing import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.infra.database.postgres import PostgresPool
from app.infra.cache.redis_client import RedisClient
from app.infra.logging.setup import configure_logging
from app.infra.cache import redis_client as redis_module
from app.infra.database import postgres as postgres_module
from app.config.settings import ServiceSettings, get_settings
from app.presentation.health.router import router as health_router


logger = structlog.get_logger(__name__)

service_settings: ServiceSettings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("application_starting", app=service_settings.APP_NAME, env=service_settings.APP_ENV)

    postgres_module.postgres_pool = PostgresPool(service_settings)
    await postgres_module.postgres_pool.connect()

    redis_module.redis_client = RedisClient(service_settings)
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
    configure_logging(service_settings)

    fastapi_app = FastAPI(
        title="Controla AI",
        description="API de gestão financeira e patrimonial com ingestão automatizada de comprovantes.",
        version="0.1.0",
        lifespan=lifespan,
        debug=service_settings.APP_DEBUG,
        docs_url=None if service_settings.is_production else "/docs",
        redoc_url=None if service_settings.is_production else "/redoc",
        openapi_url=None if service_settings.is_production else "/openapi.json",
        swagger_ui_parameters={
            "deepLinking": True,
            "defaultModelsExpandDepth": -1
        }
    )

    fastapi_app.include_router(health_router)

    return fastapi_app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=service_settings.APP_PORT,
        log_level=service_settings.LOG_LEVEL.lower()
    )
