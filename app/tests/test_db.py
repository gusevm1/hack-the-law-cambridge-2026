"""Repository unit tests — offline, with a fake session. Covers the
get_or_create_user branches incl. the UNIQUE(supabase_sub) race collapse."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

from sqlalchemy.exc import IntegrityError

from htl.db import repositories
from htl.db.models import User


class _Result:
    def __init__(self, value: Any) -> None:
        self._v = value

    def scalar_one_or_none(self) -> Any:
        return self._v


class _FakeSession:
    """Returns queued lookup results in order; optionally raises IntegrityError
    on the first flush (the lost-race case)."""

    def __init__(self, lookups: list[Any], flush_raises: bool = False) -> None:
        self._lookups = list(lookups)
        self._flush_raises = flush_raises
        self.added: list = []
        self.rolled_back = False

    async def execute(self, _stmt: Any) -> _Result:
        return _Result(self._lookups.pop(0))

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        if self._flush_raises:
            self._flush_raises = False
            raise IntegrityError("INSERT INTO users", None, Exception("duplicate key"))

    async def rollback(self) -> None:
        self.rolled_back = True


async def test_returns_existing_user_without_insert() -> None:
    existing = SimpleNamespace(id=uuid.uuid4())
    session = _FakeSession([existing])
    user = await repositories.get_or_create_user(session, supabase_sub="s", email=None)
    assert user is existing
    assert session.added == []


async def test_creates_user_on_first_sight() -> None:
    session = _FakeSession([None])
    user = await repositories.get_or_create_user(session, supabase_sub="s", email="a@b.c")
    assert isinstance(user, User)
    assert session.added == [user]


async def test_collapses_unique_race_to_the_winner() -> None:
    winner = SimpleNamespace(id=uuid.uuid4())
    # first lookup misses → insert loses the race (IntegrityError) → re-read wins
    session = _FakeSession([None, winner], flush_raises=True)
    user = await repositories.get_or_create_user(session, supabase_sub="s", email=None)
    assert user is winner
    assert session.rolled_back is True
