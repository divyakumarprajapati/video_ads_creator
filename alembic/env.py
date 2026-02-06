"""Alembic migration environment."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db.session import Base

# Import all models so they register with Base.metadata
from app.models.campaign import (  # noqa: F401
    Campaign,
    CampaignPlatformExport,
    CampaignProduct,
    CampaignVideo,
    VideoTemplate,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_sync_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


def _is_async_url(url: str | None) -> bool:
    """
    If the configured SQLAlchemy URL uses an async driver (e.g. asyncpg),
    Alembic must run migrations using SQLAlchemy's async engine helpers.
    """

    if not url:
        return False
    return "+asyncpg" in url or url.startswith("postgresql+asyncpg://")


def run_migrations_online_async() -> None:
    """
    Async migration runner for async DBAPI URLs (e.g. postgresql+asyncpg://).
    """

    def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    async def run() -> None:
        connectable = async_engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    asyncio.run(run())


if context.is_offline_mode():
    run_migrations_offline()
else:
    url = config.get_main_option("sqlalchemy.url")
    if _is_async_url(url):
        run_migrations_online_async()
    else:
        run_migrations_online()
