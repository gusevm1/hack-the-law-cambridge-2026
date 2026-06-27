"""POST /ask — the agentic citator assistant. Fully offline: the Gemini client is
faked to drive the manual function-calling loop (resolve_case → get_case_risk →
text), and resolve/case_risk are monkeypatched so no DB or Vertex call happens.
No auth override needed — the endpoint is public by design."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import htl.routes.ask as ask_route
from htl.main import app
from htl.models.api import (
    CaseRef,
    GroundTruth,
    PositiveSignal,
    ResolveResponse,
    RiskResponse,
)
from htl.routes.dependencies import get_session

ROE_RESOLVE = ResolveResponse(
    found=True,
    case_id=108713,
    case_name="Roe v. Wade",
    citation="410 U.S. 113",
    court="scotus",
    date_filed="1973-01-22",
    source="local",
)

ROE_RISK = RiskResponse(
    case=CaseRef(case_id=108713, case_name="Roe v. Wade", citation="410 U.S. 113"),
    as_of="2026-06-27",
    signal="red",
    status="overruled",
    risk_score=1.0,
    risk_rationale="Overruled by Dobbs v. Jackson Women's Health Organization.",
    trend=[],
    negative_treatments=[],
    positive_signal=PositiveSignal(approving_cites=0, total_citing=5),
    ground_truth=GroundTruth(
        on_loc_overruled_list=True,
        overruled_by="Dobbs v. Jackson Women's Health Organization",
    ),
)


def _fc(name: str, args: dict) -> SimpleNamespace:
    return SimpleNamespace(name=name, args=args)


def _resp(function_calls: list | None = None, text: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        function_calls=function_calls or [],
        text=text,
        candidates=[SimpleNamespace(content=SimpleNamespace(role="model", parts=[]))],
    )


class _FakeModels:
    """Replays a scripted sequence of model responses across the loop's rounds."""

    def __init__(self, script: list[SimpleNamespace]) -> None:
        self._script = list(script)

    async def generate_content(self, *, model, contents, config) -> SimpleNamespace:
        return self._script.pop(0)


class _FakeClient:
    def __init__(self, script: list[SimpleNamespace]) -> None:
        self.aio = SimpleNamespace(models=_FakeModels(script))


@pytest.fixture(autouse=True)
def _clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


def _client() -> TestClient:
    async def _session_override() -> AsyncIterator[object]:
        yield object()  # never touched — resolve/case_risk are monkeypatched

    app.dependency_overrides[get_session] = _session_override
    return TestClient(app)


def test_ask_runs_agentic_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    # Script: resolve_case → get_case_risk → final prose.
    script = [
        _resp(function_calls=[_fc("resolve_case", {"query": "Roe v. Wade"})]),
        _resp(function_calls=[_fc("get_case_risk", {"case_id": 108713})]),
        _resp(text="Roe v. Wade was overruled by Dobbs; do not cite it as binding. "
              "General information, not legal advice."),
    ]
    monkeypatch.setattr(ask_route, "get_client", lambda: _FakeClient(script))

    async def fake_resolve(req, session):
        assert req.query == "Roe v. Wade"
        return ROE_RESOLVE

    async def fake_case_risk(case_id, session):
        assert case_id == 108713
        return ROE_RISK

    monkeypatch.setattr(ask_route, "resolve", fake_resolve)
    monkeypatch.setattr(ask_route, "case_risk", fake_case_risk)

    r = _client().post(
        "/ask",
        json={"case": "Roe v. Wade", "use": "Cite as binding/controlling precedent"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "Dobbs" in body["answer"]
    assert body["resolved_case"]["case_id"] == 108713
    assert body["verdict"]["signal"] == "red"
    assert body["verdict"]["ground_truth"]["overruled_by"].startswith("Dobbs")


def test_ask_falls_back_to_verdict_when_no_prose(monkeypatch: pytest.MonkeyPatch) -> None:
    # The model calls the tools but the loop is exhausted before emitting text.
    script = [
        _resp(function_calls=[_fc("resolve_case", {"query": "Roe v. Wade"})]),
        _resp(function_calls=[_fc("get_case_risk", {"case_id": 108713})]),
    ] + [_resp(function_calls=[_fc("get_case_risk", {"case_id": 108713})])] * 3
    monkeypatch.setattr(ask_route, "get_client", lambda: _FakeClient(script))
    monkeypatch.setattr(ask_route, "resolve", lambda req, session: _coro(ROE_RESOLVE))
    monkeypatch.setattr(ask_route, "case_risk", lambda cid, session: _coro(ROE_RISK))

    r = _client().post("/ask", json={"case": "Roe v. Wade", "use": "Distinguish it"})
    assert r.status_code == 200
    body = r.json()
    # Fallback prose is synthesised from the verified verdict, never empty.
    assert "red" in body["answer"]
    assert body["verdict"]["signal"] == "red"


def test_ask_rejects_empty_case() -> None:
    assert _client().post("/ask", json={"case": "", "use": "x"}).status_code == 422


async def _coro(value):
    return value
