from typing import Any, Dict, List, cast

from arq import cron
from arq.typing import WorkerCoroutine

from app.config.settings import get_settings
from app.infra.cache.redis_client import RedisClient
from app.infra.database.postgres import PostgresPool
from app.infra.queue.settings import build_redis_settings
from app.config.logging_setup import configure_logging, logger
from app.infra.queue.tasks.index_pending_context import index_pending_context
from app.infra.queue.tasks.notify_due_subscriptions import notify_due_subscriptions


def _build_cron_jobs() -> List[Any]:
    """Janelas periódicas do agendador, derivadas das settings de cada módulo."""
    settings = get_settings()

    step = max(1, min(settings.RAG_INDEX_CRON_MINUTES, 60))

    return [
        cron(
            cast(WorkerCoroutine, index_pending_context),
            minute=set(range(0, 60, step)),
            run_at_startup=True,
            unique=True
        ),
        cron(
            cast(WorkerCoroutine, notify_due_subscriptions),
            hour={settings.SUBSCRIPTION_NOTIFY_CRON_HOUR},
            minute={0},
            run_at_startup=False,
            unique=True
        )
    ]


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
    on_startup = startup
    on_shutdown = shutdown
    functions: List[Any] = []
    cron_jobs: List[Any] = _build_cron_jobs()
    redis_settings = build_redis_settings()
