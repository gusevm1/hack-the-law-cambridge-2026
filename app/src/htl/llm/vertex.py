"""Gemini on Vertex AI. Auth is GCP ADC (no API key); async so one instance can
fan out many concurrent calls."""

from google import genai
from google.genai import types

from htl.settings import settings

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    # Lazy: importing this module never resolves credentials (keeps tests offline).
    global _client
    if _client is None:
        _client = genai.Client(
            vertexai=True,
            project=settings.gcp_project,
            location=settings.vertex_location,
        )
    return _client


def get_client() -> genai.Client:
    """Public accessor for the lazy Vertex client (used by the agentic /ask loop)."""
    return _get_client()


async def generate_reply(message: str, history: list[dict] | None = None) -> str:
    # Lazy import: router imports this module, so importing it at top level would
    # cycle. Route /chat through the task table ("chat") so it gets model fallback
    # and can be pointed at a pricier model without touching this code.
    from htl.llm import router

    contents: list[types.Content] = []
    for turn in history or []:
        role = "user" if turn.get("role") == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

    config = types.GenerateContentConfig(system_instruction=settings.system_prompt)
    resp = await router.generate("chat", contents=contents, config=config)
    return resp.text or ""
