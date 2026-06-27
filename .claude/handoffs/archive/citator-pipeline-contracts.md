# Citator pipeline — shared contracts (parallel build)

The source of truth for the **three parallel features** (deep-analyzer · proposition-
evolution · use-aware-verdict). Each agent builds one stage, **mocks its upstream to
the contract here**, and exposes its own contract for the next stage — exactly how
Feature 1 mocked the citations engine. Get these types right and the stages compose
on first integration.

Read alongside `citator-pipeline-scope.md` (vision, proposition spine §4, Bruen
golden example §5). Features 1 (Filter) + 2 (Classify) are **shipped + deployed**.

## The stage chain (all public, no JWT, DB-independent for now)

```
/cases/{id}/citations  (stub, done)   → Edge[]          retrieval engine (mock)
/cases/{id}/triage     (Feature 1)    → TieredEdge[]    deterministic filter
/cases/{id}/analyze    (Feature 3 = A) → AnalyzedEdge[] deep per-case LLM read
/cases/{id}/propositions (Feature 4=B) → PropositionVerdict[]  evolution + risk
POST /cases/{id}/verdict (Feature 5=C) → VerdictResponse use-aware final
```

Existing models to reuse (don't redefine): `CaseRef`, `CitingCaseRef`, `Edge`,
`TieredEdge`, `TriageSignals`, `TriageCounts` in `app/src/htl/models/api.py`; the
proposition spine in `app/src/htl/citator/propositions.py` (`PROPOSITIONS`,
`PROP_IDS`, `PHRASES`, `SPINE_TEXT`); scoring helpers (`court_weight`,
`_recency_factor`) in `citator/risk.py`; the curated-table pattern (`GROUND_TRUTH`)
in `risk.py`; the LLM pattern (Vertex + verbatim-quote check + keyword fallback) in
`llm/classify.py`.

---

## Contract A — `/cases/{id}/analyze` (Feature 3, deep analyzer)

A case can treat several propositions; deep analysis returns a *list* of findings
per edge, with the depth it actually achieved (full-text vs snippet — see the
graceful-degradation rule in the retrieval contract).

```python
class PropositionFinding(BaseModel):
    proposition: str | None      # P1..P8, or null (whole-case)
    treatment: str               # overruled|reversed|abrogated|criticised|questioned|
                                 #   limited|distinguished|followed|cited-neutral
    what_changed: str            # one line: how THIS case affects THAT proposition
    holding_vs_dicta: str        # "holding" | "dicta"
    attribution: str             # "self" | "reported"  (Rahimi "amber" trap)
    quote: str                   # verbatim span, quote-verified against the source
    confidence: float

class AnalyzedEdge(TieredEdge):   # TieredEdge + …
    analysis_depth: str          # "full-text" | "snippet"  (provenance of the read)
    findings: list[PropositionFinding]   # [] for mention edges (not analyzed)
    case_summary: str            # one-line per-case verdict on the target ("" if none)
    model: str                   # gemini id | "keyword-fallback"

class AnalyzeResponse(BaseModel):
    case: CaseRef
    total: int
    counts: TriageCounts         # carried from triage
    analyzed: int                # how many edges got the deep read (deep+shallow)
    edges: list[AnalyzedEdge]
```

## Contract B — `/cases/{id}/propositions` (Feature 4, evolution + risk)

Buckets analyzed findings by proposition, builds the evolution, quantifies risk, and
attaches the trajectory signals (circuit split · cert · close-to-overruled).

```python
class TimelinePoint(BaseModel):
    year: int
    court: str | None
    case_name: str | None
    treatment: str
    polarity: int                # -1 negative · 0 neutral · +1 approving

class CircuitSplit(BaseModel):
    present: bool
    follows: list[str]           # circuits aligned with the target
    limits: list[str]            # circuits cutting against it
    summary: str

class CertStatus(BaseModel):     # from the cert-watch table (B owns it)
    granted: bool
    case_name: str | None = None
    term: str | None = None      # e.g. "OT2025"
    question: str | None = None
    source: str | None = None    # supremecourt.gov / SCOTUSblog / CL docket
    as_of: str | None = None     # YYYY-MM-DD — staleness is explicit

class CloseToOverruled(BaseModel):
    flag: bool
    confidence: float
    rationale: str               # grounded in signals, or "needs review" on conflict

class PropositionVerdict(BaseModel):
    proposition_id: str          # P1..P8
    label: str
    summary: str
    signal: str                  # "green" | "amber" | "red" | "unknown"
    status: str                  # good | good-but-eroding | limited | overruled | …
    risk_score: float            # 0..1
    what_changed: str            # narrative of the proposition's evolution
    timeline: list[TimelinePoint]
    circuit_split: CircuitSplit | None = None
    cert: CertStatus | None = None
    close_to_overruled: CloseToOverruled
    supporting_edges: list[str]  # citing case names backing this verdict

class PropositionsResponse(BaseModel):
    case: CaseRef
    operative_rule: str          # "Bruen, good law as modified by Rahimi (2024)"
    propositions: list[PropositionVerdict]
    as_of: str
```

## Contract C — `POST /cases/{id}/verdict` (Feature 5, use-aware)

The payoff: risk **relative to the lawyer's intended use**. Maps the use (dropdown +
free-form) to the propositions it depends on, intersects with the compromised ones.

```python
class VerdictRequest(BaseModel):
    use: str = Field(min_length=1)       # the dropdown's proposition-aligned label
    intent: str = ""                     # free-form "how I'm using it" (refines)

class UseMapping(BaseModel):
    use_label: str
    intent: str
    engaged_propositions: list[str]      # P-ids the use depends on (LLM-mapped)
    rationale: str

class UseProposition(BaseModel):
    proposition_id: str
    signal: str
    relevant_to_use: bool                # is this proposition one the use depends on?
    note: str

class VerdictResponse(BaseModel):
    case: CaseRef
    operative_rule: str
    use: UseMapping
    real_risk: bool                      # engaged ∩ compromised ≠ ∅
    risk_explanation: str                # why it is / isn't real risk FOR THIS USE
    per_proposition: list[UseProposition]
    final_labels: list[str]              # ["good law as modified", "circuit split on P5",
                                         #  "cert pending on P4", "close to overruled: no"]
    close_to_overruled: CloseToOverruled
    as_of: str
```

TS mirrors (in `frontend/lib/api.ts`) must match these field-for-field.

---

## Parallelization protocol (avoid merge hell)

Shared files all three touch: `models/api.py`, `main.py`, `lib/api.ts`, and the
stepper `app/citator/analyze/page.tsx`. To keep parallel work conflict-light:

- **Backend:** each feature adds its **own route file** (`routes/analyze.py` etc.)
  and its **own `citator/` module**; appends models to `api.py` and one
  `include_router` line to `main.py` (append-only → trivial rebase).
- **Frontend:** each feature owns its **own step component file**
  (`app/citator/analyze/steps/<step>.tsx`) and appends its types to `lib/api.ts`.
  The page imports the step; touch the page minimally.
- Branch off `origin/main`; rebase/merge `main` in before opening the PR; regenerate
  lock files rather than hand-merge. Ship via the `ship-feature` skill.
- **Recommended foundation commit (do first, by the orchestrator):** land all the
  contract types above in `api.py` + `lib/api.ts` and refactor the stepper into
  per-step files, so the three agents start from a conflict-free base. The handoffs
  assume this exists; if it doesn't yet, the agent adds its own slice.

## Cross-cutting rules (scope §8)

- **LLM proposes & reads · code decides & computes · API grounds.** Risk scores are
  code, never model text. Every LLM label is schema-constrained + verbatim-quote-
  verified, or checked by a second pass.
- **Provenance non-negotiable:** every signal carries a quote + source + as_of.
- **Abstain when uncertain** (low confidence / conflicting strong signals → "needs
  review"). A confident wrong answer is the malpractice boundary — this matters most
  for `close_to_overruled` and any cert assertion (code-grounded only, never LLM).
- **Never drop.** Mentions stay surfaced and unanalyzed; nothing is hidden.
