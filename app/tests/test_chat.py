"""Chat route: gated by auth, persists both turns. Fully offline — the verifier
is overridden to the stub and the DB session to a fake recorder."""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

import htl.routes.chat as chat_route
from htl.auth.stub import STUB_USER_ID, STUB_VERIFIER
from htl.main import app
from htl.routes.dependencies import get_session, get_verifier


class FakeSession:
    def __init__(self) -> None:
        self.added: list = []
        self.commits = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1


@pytest.fixture
def fake_session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def client(fake_session: FakeSession) -> AsyncIterator[TestClient]:
    async def _session_override() -> AsyncIterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_verifier] = lambda: STUB_VERIFIER
    app.dependency_overrides[get_session] = _session_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_persists_both_turns(
    client: TestClient, fake_session: FakeSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_generate_reply(message, history):
        return f"echo: {message}"

    monkeypatch.setattr(chat_route, "generate_reply", fake_generate_reply)

    r = client.post("/chat", json={"message": "Is a verbal contract binding?"})
    assert r.status_code == 200
    assert r.json()["reply"] == "echo: Is a verbal contract binding?"
    assert r.headers["X-Correlation-ID"]  # stamped on the response

    turns = [(m.role, m.content, m.user_id) for m in fake_session.added]
    assert turns == [
        ("user", "Is a verbal contract binding?", STUB_USER_ID),
        ("assistant", "echo: Is a verbal contract binding?", STUB_USER_ID),
    ]
    # both messages carry the request's correlation id
    assert all(m.correlation_id for m in fake_session.added)
    assert fake_session.commits == 1


def test_chat_rejects_empty_message(client: TestClient) -> None:
    assert client.post("/chat", json={"message": ""}).status_code == 422
