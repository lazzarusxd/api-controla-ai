from typing import Any, Dict, List

import structlog

from app.config.settings import get_settings
from app.infra.cache.redis_client import RedisClient
from app.infra.database.postgres import PostgresPool
from app.infra.logging.setup import configure_logging
from app.infra.queue.settings import build_redis_settings

logger = structlog.get_logger(__name__)


async def startup(ctx: Dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings)

    postgres = PostgresPool(settings)
    await postgres.connect()

    redis = RedisClient(settings)
    await redis.connect()

    ctx["redis"] = redis
    ctx["settings"] = settings
    ctx["postgres"] = postgres

    logger.info("scheduler_started")


async def shutdown(ctx: Dict[str, Any]) -> None:
    redis: RedisClient = ctx.get("redis")
    postgres: PostgresPool = ctx.get("postgres")

    if redis is not None:
        await redis.disconnect()
    if postgres is not None:
        await postgres.disconnect()

    logger.info("scheduler_stopped")


class SchedulerSettings:
    functions: List[Any] = []
    cron_jobs: List[Any] = []
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = build_redis_settings()
