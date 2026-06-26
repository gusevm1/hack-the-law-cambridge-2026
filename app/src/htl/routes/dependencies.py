"""Shared FastAPI dependencies: the auth gate and a request-scoped DB session.

``CurrentUser`` is the single import a protected endpoint uses. ``get_verifier``
picks the gate by config presence (Supabase if its JWKS/issuer are set, else the
stub), cached so the ``SupabaseVerifier``'s JWKS key cache stays warm. Tests
swap either dependency via ``app.dependency_overrides`` — no monkeypatching.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from htl.auth.interface import AuthVerifier, Principal
from htl.auth.stub import STUB_VERIFIER
from htl.auth.supabase import SupabaseVerifier
from htl.db.engine import get_session_factory
from htl.settings import settings


@lru_cache(maxsize=1)
def get_verifier() -> AuthVerifier:
    if settings.supabase_jwks_url and settings.supabase_issuer:
        return SupabaseVerifier.build_from_settings(settings, get_session_factory())
    return STUB_VERIFIER


async def _resolve_user(
    verifier: Annotated[AuthVerifier, Depends(get_verifier)],
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    return await verifier.verify(authorization)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


CurrentUser = Annotated[Principal, Depends(_resolve_user)]
DbSession = Annotated[AsyncSession, Depends(get_session)]
