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


async def generate_reply(message: str, history: list[dict] | None = None) -> str:
    contents: list[types.Content] = []
    for turn in history or []:
        role = "user" if turn.get("role") == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

    resp = await _get_client().aio.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=settings.system_prompt),
    )
    return resp.text or ""
