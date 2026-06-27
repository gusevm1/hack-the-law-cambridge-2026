"""Gemini on Vertex AI. Auth is GCP ADC (no API key); async so one instance can
fan out many concurrent calls."""

from google import genai

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
