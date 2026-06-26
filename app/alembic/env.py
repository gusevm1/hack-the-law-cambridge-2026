"""Alembic environment — synchronous migration runner.

Connects the same two ways as the runtime (settings-driven): Cloud SQL via the
connector (pg8000, sync) when INSTANCE_CONNECTION_NAME is set, else DATABASE_URL.
The async runtime path (asyncpg) never touches this file.
"""

from __future__ import annotations

from typing import Any

from alembic import context
from sqlalchemy import Engine, create_engine, pool

# Import the models package so every mapped class registers on Base.metadata
# before autogenerate compares against the live DB.
from htl.db import Base
from htl.settings import settings

config = context.config
target_metadata = Base.metadata


def _make_engine() -> Engine:
    if settings.instance_connection_name:
        from google.cloud.sql.connector import Connector

        connector = Connector()

        def getconn() -> Any:
            return connector.connect(
                settings.instance_connection_name,
                "pg8000",
                user=settings.db_user,
                password=settings.db_password,
                db=settings.db_name,
            )

        return create_engine("postgresql+pg8000://", creator=getconn, poolclass=pool.NullPool)

    if settings.database_url:
        sync_url = settings.database_url.replace("+asyncpg", "+pg8000")
        return create_engine(sync_url, poolclass=pool.NullPool)

    raise RuntimeError("No database configured: set INSTANCE_CONNECTION_NAME or DATABASE_URL.")


def run_migrations_online() -> None:
    with _make_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
