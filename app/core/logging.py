"""
Structured logging setup using *structlog*.

Every log entry is emitted as JSON in production and as coloured key=value
pairs during development, making it easy to pipe into any log aggregator.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.is_production:
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(
            structlog.dev.ConsoleRenderer(colors=True)
        )

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, settings.log_level))
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    if not root.handlers:
        root.addHandler(handler)

    def _set_logger_level(name: str, level: int) -> None:
        """Set logger + its handlers to *level* (some libs attach their own handlers)."""
        log = logging.getLogger(name)
        log.setLevel(level)
        for h in log.handlers:
            h.setLevel(level)

    # Quieten noisy libraries.
    # Note: SQLAlchemy `echo=True` will still force SQL logs on; keep DB echo off by default.
    noisy_libs = (
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "asyncpg",
        "httpx",
        "openai",
        "botocore",
        "boto3",
        "urllib3",
    )
    for lib in noisy_libs:
        _set_logger_level(lib, logging.ERROR)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structured logger bound to *name*."""
    return structlog.get_logger(name or __name__)
