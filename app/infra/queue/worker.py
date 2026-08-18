from typing import Any, Dict, List

from app.config.settings import get_settings
from app.infra.cache.redis_client import RedisClient
from app.infra.database.postgres import PostgresPool
from app.infra.queue.settings import build_redis_settings
from app.config.logging_setup import configure_logging, logger
from app.infra.queue.tasks.process_receipt import process_receipt


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

    logger.info("worker_started")


async def shutdown(ctx: Dict[str, Any]) -> None:
    redis: RedisClient = ctx.get("redis")
    postgres: PostgresPool = ctx.get("postgres")

    if redis is not None:
        await redis.disconnect()
    if postgres is not None:
        await postgres.disconnect()

    logger.info("worker_stopped")


class WorkerSettings:
    max_tries = 3
    max_jobs = 10
    job_timeout = 300
    keep_result = 3600
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = build_redis_settings()
    functions: List[Any] = [process_receipt]
