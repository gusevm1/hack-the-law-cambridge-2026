"""Data access for users + messages. Plain functions over an ``AsyncSession`` —
the caller owns the transaction (commit/rollback)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from htl.db.models import Message, User


async def _by_sub(session: AsyncSession, supabase_sub: str) -> User | None:
    result = await session.execute(select(User).where(User.supabase_sub == supabase_sub))
    return result.scalar_one_or_none()


async def get_or_create_user(session: AsyncSession, *, supabase_sub: str, email: str | None) -> User:
    """Return the user for this Supabase ``sub``, creating it on first sight.

    The UNIQUE(supabase_sub) constraint collapses the race when two concurrent
    first requests for the same new user both try to insert: the loser catches
    IntegrityError, rolls back, and re-reads the winner.
    """
    existing = await _by_sub(session, supabase_sub)
    if existing is not None:
        return existing

    user = User(supabase_sub=supabase_sub, email=email)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        winner = await _by_sub(session, supabase_sub)
        if winner is None:  # pragma: no cover — UNIQUE guarantees it exists now
            raise
        return winner
    return user


async def add_message(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    role: str,
    content: str,
    correlation_id: str | None,
) -> Message:
    message = Message(user_id=user_id, role=role, content=content, correlation_id=correlation_id)
    session.add(message)
    await session.flush()
    return message
