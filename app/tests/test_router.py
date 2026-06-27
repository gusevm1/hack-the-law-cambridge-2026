"""Task → model router — offline (no live LLM). Covers prefix→provider/location
inference, model_for (table + env override), and the model-fallback chain: a
preview model that 404s degrades to its GA fallback, and a claude-* route (not
wired here) degrades to Gemini via settings.model_fallbacks."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import htl.llm.router as router
import htl.llm.vertex as vertex
from htl.settings import settings


class _Models:
    """Fake genai models surface: records called model ids, fails a chosen set."""

    def __init__(self, fail: set[str]) -> None:
        self.fail = set(fail)
        self.calls: list[str] = []

    async def generate_content(self, *, model, contents, config) -> SimpleNamespace:
        self.calls.append(model)
        if model in self.fail:
            raise RuntimeError("simulated 404 / model not enabled")
        return SimpleNamespace(text='{"ok": true}')


class _Client:
    def __init__(self, fail: set[str] = frozenset()) -> None:
        self.models = _Models(set(fail))
        self.aio = SimpleNamespace(models=self.models)


def test_provider_of_by_prefix() -> None:
    assert router.provider_of("gemini-2.5-flash") == "gemini"
    assert router.provider_of("claude-opus-4-8") == "claude"
    assert router.provider_of("deepseek-r1-0528-maas") == "maas"
    assert router.provider_of("gpt-oss-120b-maas") == "maas"


def test_location_for_pins_provider_region() -> None:
    assert router.location_for("gemini-2.5-flash") == settings.vertex_location  # global
    assert router.location_for("claude-opus-4-8") == settings.claude_location  # us-central1
    assert router.location_for("gpt-oss-120b-maas") == settings.maas_location  # us-central1


def test_model_for_table_and_default() -> None:
    assert router.model_for("classify") == settings.model_routes["classify"]
    assert router.model_for("ask") == settings.model_routes["ask"]
    # Unmapped task → the Gemini default, never a crash.
    assert router.model_for("does-not-exist") == settings.gemini_model


def test_model_for_env_override(monkeypatch) -> None:
    monkeypatch.setenv("HTL_MODEL_CLASSIFY", "gemini-3.5-flash")
    assert router.model_for("classify") == "gemini-3.5-flash"  # env beats the table


def test_complete_returns_parsed_json(monkeypatch) -> None:
    client = _Client()
    monkeypatch.setattr(vertex, "_get_client", lambda: client)
    out = asyncio.run(router.complete("classify", system="s", prompt="p", schema={"type": "OBJECT"}))
    assert out == {"ok": True}
    assert client.models.calls == [settings.model_routes["classify"]]


def test_fallback_fires_on_error(monkeypatch) -> None:
    # analyze → gemini-3.1-pro-preview (fails) → fallback gemini-2.5-pro (succeeds).
    primary = settings.model_routes["analyze"]
    fallback = settings.model_fallbacks[primary]
    client = _Client(fail={primary})
    monkeypatch.setattr(vertex, "_get_client", lambda: client)

    out = asyncio.run(router.complete("analyze", system="s", prompt="p", schema={"type": "OBJECT"}))
    assert out == {"ok": True}
    assert client.models.calls == [primary, fallback]  # tried primary, then fell back


def test_claude_route_degrades_to_gemini(monkeypatch) -> None:
    # A claude-* route is "behind config" — not wired here, so its dispatch raises;
    # the fallback chain routes it to Gemini, which answers. Claude never hits the client.
    monkeypatch.setenv("HTL_MODEL_CLASSIFY", "claude-opus-4-8")
    client = _Client()
    monkeypatch.setattr(vertex, "_get_client", lambda: client)

    out = asyncio.run(router.complete("classify", system="s", prompt="p", schema={"type": "OBJECT"}))
    assert out == {"ok": True}
    assert client.models.calls == [settings.model_fallbacks["claude-opus-4-8"]]  # gemini only
