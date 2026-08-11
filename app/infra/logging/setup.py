import sys
import logging
from typing import Any, List

import structlog

from app.config.settings import Settings


def configure_logging(settings: Settings) -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper())

    logging.basicConfig(
        force=True,
        level=level,
        stream=sys.stdout,
        format="%(message)s"
    )

    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "gunicorn"):
        noisy_logger = logging.getLogger(logger_name)
        noisy_logger.handlers.clear()
        noisy_logger.propagate = True

    processors: List[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.is_production:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        cache_logger_on_first_use=True,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level)
    )
