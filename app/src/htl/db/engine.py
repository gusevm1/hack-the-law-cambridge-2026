"""Async SQLAlchemy engine + session factory.

Two ways to reach Postgres, picked by config:

- **Cloud SQL** (prod + local-against-cloud): the Cloud SQL Python connector
  dials the instance over IAM (no proxy, no IP allowlist) using asyncpg. Auth is
  ADC — the Cloud Run runtime SA in prod, your ``gcloud`` ADC locally.
- **DATABASE_URL** (plain Postgres): a direct async URL, handy for a local
  container.

Everything is lazy + cached: importing this module resolves no credentials and
opens no socket, so the test suite (which overrides the session dependency)
never touches a database.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from htl.settings import settings

# Held so the lifespan can close the connector's background tasks on shutdown.
_connector: Any = None


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    if settings.instance_connection_name:
        from google.cloud.sql.connector import Connector

        global _connector
        _connector = Connector()

        async def getconn() -> Any:
            return await _connector.connect_async(
                settings.instance_connection_name,
                "asyncpg",
                user=settings.db_user,
                password=settings.db_password,
                db=settings.db_name,
            )

        return create_async_engine(
            "postgresql+asyncpg://", async_creator=getconn, pool_pre_ping=True
        )

    if settings.database_url:
        return create_async_engine(settings.database_url, pool_pre_ping=True)

    raise RuntimeError(
        "No database configured: set INSTANCE_CONNECTION_NAME (Cloud SQL) or DATABASE_URL."
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)


async def dispose_engine() -> None:
    """Dispose the pool and close the Cloud SQL connector (lifespan shutdown)."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    if _connector is not None:
        await _connector.close_async()
