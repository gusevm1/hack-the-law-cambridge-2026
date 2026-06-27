"""Offline DB stub for the test suite.

The citator routes now take a ``DbSession`` and read real edges from Postgres, with
the Bruen golden stub as the fallback when the DB has nothing for an id. Tests run
with no Postgres, so override ``get_session`` with a session whose every query comes
back empty — every route falls through to the golden path, exactly as before the
wire. (DB-assembly itself is exercised live, per the repo's existing pattern.)
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from htl.main import app
from htl.routes.dependencies import get_session


class _EmptyResult:
    def scalars(self) -> "_EmptyResult":
        return self

    def first(self) -> None:
        return None

    def all(self) -> list:
        return []


class _EmptySession:
    """Returns no rows / zero counts for any query — drives the golden fallback."""

    async def execute(self, *_args: object, **_kwargs: object) -> _EmptyResult:
        return _EmptyResult()

    async def scalar(self, *_args: object, **_kwargs: object) -> int:
        return 0


async def _empty_session() -> AsyncIterator[_EmptySession]:
    yield _EmptySession()


@pytest.fixture(autouse=True)
def _stub_db() -> AsyncIterator[None]:
    app.dependency_overrides[get_session] = _empty_session
    yield
    app.dependency_overrides.pop(get_session, None)
