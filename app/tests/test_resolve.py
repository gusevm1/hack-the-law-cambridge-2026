"""POST /resolve — citator lookup. Fully offline: the DB session is a fake
recorder and the CourtListener HTTP call is monkeypatched. No auth override
needed — the endpoint is public by design."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import htl.routes.resolve as resolve_route
from htl.main import app
from htl.routes.dependencies import get_session


class _FakeResult:
    def __init__(self, row: object | None) -> None:
        self._row = row

    def scalars(self) -> _FakeResult:
        return self

    def first(self) -> object | None:
        return self._row


class FakeSession:
    """Returns the queued rows on successive ``execute`` calls (citation, then name)."""

    def __init__(self, rows: list[object | None]) -> None:
        self._rows = list(rows)

    async def execute(self, _stmt: object) -> _FakeResult:
        return _FakeResult(self._rows.pop(0) if self._rows else None)


def _client(rows: list[object | None]) -> TestClient:
    async def _session_override() -> AsyncIterator[FakeSession]:
        yield FakeSession(rows)

    app.dependency_overrides[get_session] = _session_override
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


def _must_not_call(_query: str) -> dict:
    raise AssertionError("CL search must not run on a local DB hit")


ROE = SimpleNamespace(
    id=108713,
    case_name="Roe v. Wade",
    citation="410 U.S. 113",
    court="scotus",
    date_filed=date(1973, 1, 22),
)


def test_resolve_local_hit_by_citation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolve_route, "cl_search", _must_not_call)
    r = _client([ROE]).post("/resolve", json={"query": "410 U.S. 113"})
    assert r.status_code == 200
    assert r.json() == {
        "found": True,
        "case_id": 108713,
        "case_name": "Roe v. Wade",
        "citation": "410 U.S. 113",
        "court": "scotus",
        "date_filed": "1973-01-22",
        "source": "local",
        "ambiguous": False,
    }


def test_resolve_local_hit_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolve_route, "cl_search", _must_not_call)
    # citation miss (None) → name hit (ROE)
    r = _client([None, ROE]).post("/resolve", json={"query": "Roe v. Wade"})
    body = r.json()
    assert body["found"] is True
    assert body["case_id"] == 108713
    assert body["source"] == "local"


def test_resolve_nonsense_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolve_route, "cl_search", lambda _q: {"results": []})
    r = _client([None, None]).post("/resolve", json={"query": "qwerty nonsense xyz"})
    assert r.json() == {
        "found": False,
        "case_id": None,
        "case_name": None,
        "citation": None,
        "court": None,
        "date_filed": None,
        "source": None,
        "ambiguous": False,
    }


def test_resolve_cl_search_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "results": [
            {
                "cluster_id": 108713,
                "caseName": "Roe v. Wade",
                "court_id": "scotus",
                "citation": ["35 L. Ed. 2d 147", "410 U.S. 113"],
                "dateFiled": "1973-01-22T00:00:00",
            }
        ]
    }
    monkeypatch.setattr(resolve_route, "cl_search", lambda _q: payload)
    r = _client([None, None]).post("/resolve", json={"query": "410 U.S. 113"})
    body = r.json()
    assert body["found"] is True
    assert body["case_id"] == 108713  # the CL cluster id, from the mocked search
    assert body["source"] == "cl_search"
    assert body["citation"] == "410 U.S. 113"  # U.S. Reports cite preferred
    assert body["ambiguous"] is False


def test_resolve_rejects_empty_query() -> None:
    assert _client([]).post("/resolve", json={"query": ""}).status_code == 422
