from fastapi.testclient import TestClient

import htl.routes.chat as chat_route
from htl.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_returns_reply(monkeypatch):
    async def fake_generate_reply(message, history):
        assert history == []
        return f"echo: {message}"

    monkeypatch.setattr(chat_route, "generate_reply", fake_generate_reply)

    r = client.post("/chat", json={"message": "Is a verbal contract binding?"})
    assert r.status_code == 200
    assert r.json()["reply"] == "echo: Is a verbal contract binding?"


def test_chat_rejects_empty_message():
    assert client.post("/chat", json={"message": ""}).status_code == 422
