"""Database package: declarative base, ORM models, async engine, repositories."""

from htl.db.base import Base

# Import models so they register on Base.metadata (alembic autogenerate + create_all).
from htl.db import models as models  # noqa: F401

__all__ = ["Base"]
