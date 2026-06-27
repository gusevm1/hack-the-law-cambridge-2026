"""Task → model router.

One settings table maps a logical task to a model id; the provider — and thus the
Vertex location and client — is inferred from the model-id prefix:

    gemini-*  → gemini / global        (the default; the only provider callable here)
    claude-*  → claude / us-central1   (Anthropic partner models; behind config)
    <other>   → maas   / us-central1   (open Model-as-a-Service, e.g. deepseek/gpt-oss)

``complete()`` dispatches a single schema/text call (classify & the other snippet
tasks); the agentic ``/ask`` loop uses ``generate()`` for a raw genai response so it
keeps its function-calling shape. Both walk ``settings.model_fallbacks`` when the
chosen model errors (404 / quota / not-enabled), so a route to an un-enabled Claude
model *degrades to Gemini* instead of failing.

ponytail: a settings dict + a dispatch fn + a fallback chain. No provider-plugin
framework. Only Gemini is wired today — claude/maas are 404-blocked on this project
until a console Model-Garden enablement (see handoffs/vertex-models.md), so their
dispatch is an explicit wire-point the fallback chain routes around. Wire
``AnthropicVertex`` (us-central1) / the OpenAI-compat MaaS endpoint there once enabled.
"""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from typing import Any

from google.genai import types

from htl.llm import vertex
from htl.settings import settings


def provider_of(model: str) -> str:
    """Infer the provider from the model-id prefix."""
    m = (model or "").lower()
    if m.startswith("gemini"):
        return "gemini"
    if m.startswith("claude"):
        return "claude"
    return "maas"  # open Model-as-a-Service (deepseek-*, gpt-oss-*, llama-*, …)


def location_for(model: str) -> str:
    """The Vertex location the model's provider lives at (account-portable: all via settings)."""
    return {
        "gemini": settings.vertex_location,
        "claude": settings.claude_location,
        "maas": settings.maas_location,
    }[provider_of(model)]


def model_for(task: str) -> str:
    """Configured model for a task: per-task env override > table > Gemini default.

    The env override (``HTL_MODEL_<TASK>``, e.g. ``HTL_MODEL_ANALYZE=claude-opus-4-8``)
    keeps routing account-portable — no model id is hardcoded in feature code.
    """
    return os.environ.get(f"HTL_MODEL_{task.upper()}") or settings.model_routes.get(
        task, settings.gemini_model
    )


async def _with_fallback(task: str, call: Callable[[str], Awaitable[Any]]) -> Any:
    """Run ``call(model)``; on any error hop to ``model_fallbacks[model]`` and retry,
    until the chain is exhausted — then re-raise so the caller can degrade (the
    keyword classifier / verdict synthesis still sit above this)."""
    model = model_for(task)
    tried: set[str] = set()
    while True:
        tried.add(model)
        try:
            return await call(model)
        except Exception:
            nxt = settings.model_fallbacks.get(model)
            if not nxt or nxt in tried:
                raise
            model = nxt


async def generate(task: str, *, contents: Any, config: Any = None) -> Any:
    """Raw Gemini ``generate_content`` for ``task`` with model fallback; returns the
    genai response. For the agentic ``/ask`` loop, which needs genai-shaped contents
    and tool calls (so it is Gemini-only by design)."""
    return await _with_fallback(
        task,
        lambda model: vertex._get_client().aio.models.generate_content(
            model=model, contents=contents, config=config
        ),
    )


async def complete(
    task: str,
    *,
    system: str,
    prompt: str,
    schema: dict | None = None,
    temperature: float = 0.0,
) -> str | dict:
    """Single-shot completion for ``task``. Returns the schema-validated JSON (a dict)
    when ``schema`` is given, else the text. Routes by provider; falls back on error."""
    return await _with_fallback(
        task,
        lambda model: _dispatch(
            model, system=system, prompt=prompt, schema=schema, temperature=temperature
        ),
    )


async def _dispatch(
    model: str, *, system: str, prompt: str, schema: dict | None, temperature: float
) -> str | dict:
    if provider_of(model) == "gemini":
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            **(
                {"response_mime_type": "application/json", "response_schema": schema}
                if schema
                else {}
            ),
        )
        resp = await vertex._get_client().aio.models.generate_content(
            model=model, contents=prompt, config=config
        )
        text = resp.text or ""
        return json.loads(text or "{}") if schema else text

    # ponytail: claude (AnthropicVertex @ us-central1) and open MaaS (OpenAI-compat
    # endpoint) are 404-blocked on this project until a console enablement, so they
    # can't be exercised/tested here. Leave the wire-point explicit; the fallback
    # chain (settings.model_fallbacks) degrades a claude/maas route to Gemini until
    # this is wired. Upgrade path: AnthropicVertex.messages / httpx POST + ADC token.
    raise NotImplementedError(
        f"provider {provider_of(model)!r} ({model} @ {location_for(model)}) not wired; "
        "enable it in Model Garden and dispatch here — see handoffs/vertex-models.md."
    )
