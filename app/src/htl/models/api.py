from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatTurn] = []


class ChatResponse(BaseModel):
    reply: str


class ResolveRequest(BaseModel):
    query: str = Field(min_length=1)  # a reporter citation or a case name


class ResolveResponse(BaseModel):
    """Citator lookup result. ``found=false`` with nulls is the anti-hallucination
    gate — we never invent a case. ``case_id`` is the CourtListener *cluster id*
    (same id space as ``citation_edges.cited_id``) so it can feed ``/cases/{id}/risk``."""

    found: bool
    case_id: int | None = None
    case_name: str | None = None
    citation: str | None = None
    court: str | None = None
    date_filed: str | None = None
    source: str | None = None  # "local" | "cl_search" | None
    ambiguous: bool = False
