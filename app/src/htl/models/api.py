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
    treatment: str | None = None  # persisted classification (most severe per citer), if any


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


# =========================================================================== #
# Pipeline contracts — Features 3–5 (deep-analyze · propositions · verdict).   #
# Defined up front so the three parallel features build to IDENTICAL shapes and
# compose on integration. Routes + logic land with each feature. See
# .claude/handoffs/citator-pipeline-contracts.md.
# =========================================================================== #


# --- Feature 3 (A): GET /cases/{id}/analyze — deep per-case analysis -------- #
class PropositionFinding(BaseModel):
    """How one citing case treats ONE proposition of the target."""

    proposition: str | None = None  # P1..P8, or null (whole-case)
    treatment: str  # overruled | limited | followed | cited-neutral | …
    what_changed: str  # one line: how this case affects that proposition
    holding_vs_dicta: str  # "holding" | "dicta"
    attribution: str  # "self" | "reported"
    quote: str  # verbatim span, quote-verified against the source
    confidence: float


class AnalyzedEdge(TieredEdge):
    """A tiered edge with its deep read. One case can touch several propositions, so
    ``findings`` is a list. ``mention`` edges aren't analyzed (``findings=[]``)."""

    analysis_depth: str  # "full-text" | "snippet" — provenance of the read
    findings: list[PropositionFinding] = []
    case_summary: str = ""  # one-line per-case verdict on the target
    model: str  # gemini id | "keyword-fallback"


class AnalyzeResponse(BaseModel):
    case: CaseRef
    total: int
    counts: TriageCounts
    analyzed: int  # edges that got the deep read (deep + shallow, non-neutral)
    skipped_neutral: int = 0  # worth-it tier but cited the target neutrally → not read
    edges: list[AnalyzedEdge]


# --- Feature 4 (B): GET /cases/{id}/propositions — evolution + risk --------- #
class TimelinePoint(BaseModel):
    year: int
    court: str | None = None
    case_name: str | None = None
    treatment: str
    polarity: int  # -1 negative · 0 neutral · +1 approving


class CircuitSplit(BaseModel):
    present: bool
    follows: list[str] = []  # circuits aligned with the target
    limits: list[str] = []  # circuits cutting against it
    summary: str = ""


class CertStatus(BaseModel):
    """SCOTUS review status — code/curated-grounded only, never LLM-asserted."""

    granted: bool
    case_name: str | None = None
    term: str | None = None  # e.g. "OT2025"
    question: str | None = None
    source: str | None = None  # supremecourt.gov / SCOTUSblog / CL docket
    as_of: str | None = None  # YYYY-MM-DD — staleness is explicit


class CloseToOverruled(BaseModel):
    flag: bool
    confidence: float
    rationale: str  # grounded in signals, or "needs review" on conflict


class PropositionVerdict(BaseModel):
    proposition_id: str  # P1..P8
    label: str
    summary: str
    signal: str  # "green" | "amber" | "red" | "unknown"
    status: str  # good | good-but-eroding | limited | overruled | …
    risk_score: float  # 0..1
    what_changed: str  # narrative of the proposition's evolution
    timeline: list[TimelinePoint] = []
    circuit_split: CircuitSplit | None = None
    cert: CertStatus | None = None
    close_to_overruled: CloseToOverruled
    supporting_edges: list[str] = []  # citing case names backing this verdict


class PropositionsResponse(BaseModel):
    case: CaseRef
    operative_rule: str  # "Bruen, good law as modified by Rahimi (2024)"
    propositions: list[PropositionVerdict]
    as_of: str


# --- Feature 5 (C): POST /cases/{id}/verdict — use-aware verdict ------------ #
class VerdictRequest(BaseModel):
    use: str = Field(min_length=1)  # the dropdown's proposition-aligned label
    intent: str = ""  # free-form "how I'm using it" (refines)


class UseMapping(BaseModel):
    use_label: str
    intent: str
    engaged_propositions: list[str] = []  # P-ids the use depends on
    rationale: str


class UseProposition(BaseModel):
    proposition_id: str
    signal: str
    relevant_to_use: bool  # is this a proposition the use depends on?
    note: str


class VerdictResponse(BaseModel):
    case: CaseRef
    operative_rule: str
    use: UseMapping
    real_risk: bool  # engaged ∩ compromised ≠ ∅
    risk_explanation: str  # why it is / isn't real risk FOR THIS USE
    per_proposition: list[UseProposition] = []
    final_labels: list[str] = []
    close_to_overruled: CloseToOverruled
    as_of: str


# --- GET /cases/{id}/graph — the treatment network -------------------------- #
class GraphNode(BaseModel):
    """One case in the citation network: the focal authority or one of its citers."""

    case_id: int
    case_name: str | None = None
    citation: str | None = None
    court: str | None = None
    date_filed: str | None = None
    is_focal: bool = False


class GraphEdge(BaseModel):
    """A citing→cited edge, carrying the treatment that grounds its colour. One edge
    per citer (the most severe / most confident treatment when several exist).
    ``treatment=None`` is a neutral citation — cited but not treated."""

    citing_id: int
    cited_id: int
    treatment: str | None = None  # overruled | distinguished | followed | … | None
    polarity: str = "neutral"  # "negative" | "positive" | "neutral"
    confidence: float | None = None
    quote: str | None = None
    on_other_grounds: bool = False
    source_url: str | None = None  # deep link to the citing opinion (the receipt)


class GraphResponse(BaseModel):
    """The focal case + its inbound treatment network, for the graph view. Pairs
    with /risk: /risk is the verdict, /graph is the evidence you can click."""

    focal: CaseRef
    signal: str  # mirrors /risk: red | amber | green | unknown
    nodes: list[GraphNode]
    edges: list[GraphEdge]
