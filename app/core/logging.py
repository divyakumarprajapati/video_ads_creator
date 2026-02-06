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

    # Quieten noisy libraries
    for lib in ("uvicorn.access", "sqlalchemy.engine", "botocore", "urllib3"):
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structured logger bound to *name*."""
    return structlog.get_logger(name or __name__)
