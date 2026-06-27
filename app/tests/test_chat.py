"""POST /chat — the citator-aware conversational assistant. Fully offline: the
Gemini client is faked to drive the manual function-calling loop, and the citator
tools (resolve/risk/propositions) are monkeypatched so no DB or Vertex call runs.
Public by design — no auth override needed."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import htl.llm.vertex as vertex
import htl.routes.chat as chat_route
from htl.main import app
from htl.models.api import CaseRef, PropositionsResponse, PropositionVerdict, CloseToOverruled
from htl.routes.dependencies import get_session

BRUEN_PROPS = PropositionsResponse(
    case=CaseRef(case_id=6480696, case_name="NYSRPA v. Bruen"),
    operative_rule="Bruen, good law as modified by Rahimi (2024).",
    propositions=[
        PropositionVerdict(
            proposition_id="P2a",
            label="Analogue not twin",
            summary="The historical analogue need only be relevantly similar.",
            signal="amber",
            status="limited",
            risk_score=0.4,
            what_changed="Rahimi rejected the 'dead ringer' reading; relevantly similar suffices.",
            close_to_overruled=CloseToOverruled(flag=False, confidence=0.0, rationale=""),
        )
    ],
    as_of="2026-06-27",
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
        yield object()  # never touched — the tools are monkeypatched

    app.dependency_overrides[get_session] = _session_override
    return TestClient(app)


async def _coro(value):
    return value


def test_health() -> None:
    assert _client().get("/health").json() == {"status": "ok"}


def test_chat_reads_propositions_for_doctrinal_question(monkeypatch: pytest.MonkeyPatch) -> None:
    # Script: resolve Bruen → read its propositions → synthesise the current test.
    script = [
        _resp(function_calls=[_fc("get_case_propositions", {"case_id": 6480696})]),
        _resp(text="The current test is a relevantly similar historical analogue, "
              "loosened by Rahimi. General information, not legal advice."),
    ]
    fake = _FakeClient(script)  # one instance: the router re-fetches the client each round
    monkeypatch.setattr(vertex, "_get_client", lambda: fake)
    monkeypatch.setattr(chat_route, "case_propositions", lambda cid: _coro(BRUEN_PROPS))

    r = _client().post(
        "/chat", json={"message": "What is the current test under Bruen?"}
    )
    assert r.status_code == 200
    assert "Rahimi" in r.json()["reply"]
    assert r.headers["X-Correlation-ID"]


def test_chat_preloads_case_scoped_propositions(monkeypatch: pytest.MonkeyPatch) -> None:
    # case_id set → propositions are pre-loaded; the model answers without a tool call.
    seen: dict = {}

    async def fake_props(case_id):
        seen["case_id"] = case_id
        return BRUEN_PROPS

    fake = _FakeClient([_resp(text="P2a is amber.")])
    monkeypatch.setattr(vertex, "_get_client", lambda: fake)
    monkeypatch.setattr(chat_route, "case_propositions", fake_props)

    r = _client().post("/chat", json={"message": "Why is P2a amber?", "case_id": 6480696})
    assert r.status_code == 200
    assert r.json()["reply"] == "P2a is amber."
    assert seen["case_id"] == 6480696  # pre-loaded for the on-screen case


def test_chat_rejects_empty_message() -> None:
    assert _client().post("/chat", json={"message": ""}).status_code == 422
