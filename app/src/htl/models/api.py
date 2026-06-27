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


# --- POST /ask — agentic citator-aware assistant ---------------------------- #
class AskRequest(BaseModel):
    case: str = Field(min_length=1)  # free-form case text (name and/or citation)
    use: str = Field(min_length=1)  # how the litigator intends to use it in court


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


class AskResponse(BaseModel):
    """Agentic /ask result: the grounded prose answer plus the *real* citator data
    the agent pulled (resolve + risk), so the frontend renders the verdict card
    from verified facts regardless of what the prose says."""

    answer: str
    resolved_case: ResolveResponse | None = None
    verdict: RiskResponse | None = None


# --- GET /cases/{id}/citations — inbound citation edges (retrieval stub) ----- #
class Edge(BaseModel):
    """One retrieved inbound citation. Contract mirrors the (assumed) retrieval
    engine output: full-text ∪ graph union, deduped by cluster, each edge carrying
    provenance (``source`` + ``matched_citation`` + ``opinion_url``)."""

    citing_case: CitingCaseRef
    citation: str | None = None
    passage: str  # the citing passage / snippet
    source: str  # "graph" | "fulltext"
    matched_citation: str | None = None  # which parallel cite matched
    opinion_url: str | None = None


class CitationsResponse(BaseModel):
    case: CaseRef
    total: int
    edges: list[Edge]


# --- GET /cases/{id}/triage — deterministic depth-of-analysis tiering -------- #
class TriageSignals(BaseModel):
    """The deterministic signals the tier was computed from (auditable)."""

    binding: bool  # citing court binds the target (apex or federal circuit)
    treatment_kw: list[str]  # treatment-language keywords matched in the passage
    propositions_engaged: list[str]  # proposition ids (P1..P8) with a phrase hit
    recency_years: int  # how many years ago the citing opinion was filed


class TieredEdge(Edge):
    """An ``Edge`` tagged with its triage tier. NEVER dropped — noise is
    surfaced as ``mention``, low-ranked, not hidden."""

    tier: str  # "deep" | "shallow" | "mention"
    reasons: list[str]
    signals: TriageSignals


class TriageCounts(BaseModel):
    deep: int
    shallow: int
    mention: int


class TriageResponse(BaseModel):
    case: CaseRef
    total: int
    counts: TriageCounts
    edges: list[TieredEdge]


# --- GET /cases/{id}/classify — per-edge proposition-level treatment -------- #
class EdgeClassification(BaseModel):
    """The LLM's read of one edge: what treatment, which proposition, holding vs
    dicta, who did it (self vs reported), the verbatim justifying span, and how
    confident — schema-constrained + quote-verified (code decides, model reads)."""

    treatment: str  # overruled | limited | followed | cited-neutral | …
    proposition: str | None = None  # spine id (P1..P8) it hits, or null (whole-case)
    holding_vs_dicta: str  # "holding" | "dicta"
    attribution: str  # "self" | "reported"
    quote: str  # verbatim span from the passage
    confidence: float
    model: str  # gemini model id, or "keyword-fallback"


class ClassifiedEdge(TieredEdge):
    """A tiered edge plus its classification. ``mention`` edges are surfaced but not
    classified (``classification=null``) — the filter already judged them noise."""

    classification: EdgeClassification | None = None


class ClassifyResponse(BaseModel):
    case: CaseRef
    total: int
    counts: TriageCounts
    classified: int  # how many edges got the LLM (deep + shallow)
    edges: list[ClassifiedEdge]
