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


# --- GET /cases/{id}/risk --------------------------------------------------- #
class CaseRef(BaseModel):
    case_id: int
    case_name: str | None = None
    citation: str | None = None
    court: str | None = None
    date_filed: str | None = None


class TrendPoint(BaseModel):
    """One year on the erosion curve: counts of negative vs positive treatments."""

    year: int
    neg: int
    pos: int
    neg_share: float  # neg / (neg + pos)


class CitingCaseRef(BaseModel):
    case_name: str | None = None
    court: str | None = None
    date_filed: str | None = None


class NegativeTreatment(BaseModel):
    citing_case: CitingCaseRef
    type: str
    scope: str | None = None
    on_other_grounds: bool = False
    quote: str | None = None
    confidence: float | None = None


class PositiveSignal(BaseModel):
    approving_cites: int  # citers that 'followed' the case
    total_citing: int  # all inbound citations on record


class GroundTruth(BaseModel):
    """Curated against the Library of Congress 'Decisions Overruled' table (stub)."""

    on_loc_overruled_list: bool
    overruled_by: str | None = None


class RiskResponse(BaseModel):
    """The citator verdict for a case: is it still good law, and how exposed?"""

    case: CaseRef
    as_of: str  # YYYY-MM-DD
    signal: str  # "red" | "amber" | "green" | "unknown"
    status: str  # "overruled" | "good-but-eroding" | "good" | "unknown"
    risk_score: float  # 0.0 (safe) .. 1.0 (overruled)
    risk_rationale: str
    trend: list[TrendPoint]
    negative_treatments: list[NegativeTreatment]
    positive_signal: PositiveSignal
    ground_truth: GroundTruth
