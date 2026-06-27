"""Deep per-case analyzer — Feature 3 (A) of the proposition-level citator.

Given a citing edge to the target, read the citing opinion and emit **per-
proposition findings**: one case can touch several of the target's propositions
(treatment · what_changed · holding/dicta · attribution · verbatim quote · conf),
plus a one-line ``case_summary``. This supersedes the depth of Feature 2's
``/classify`` (snippet-only) — it reuses ``classify_edge`` as the snippet path.

**Graceful degradation** is the core design. Full opinion text is only sometimes
available (retrieval persists it in ``cl_opinions.plain_text``; recent F.4th cases
often come back empty):

- **full-text mode** — the opinion text is present → one deep, schema-constrained
  read that locates every passage discussing the target across the whole opinion,
  classifies each per proposition, and compiles a list of findings + a case
  summary. ``analysis_depth="full-text"``.
- **snippet mode** — only the edge ``passage`` snippet exists → fall back to the
  Feature-2 ``classify_edge`` path, wrap it as a single finding with **lowered
  confidence**. ``analysis_depth="snippet"``. Never pretend to depth we didn't have.

Same discipline as ``llm.classify``: Vertex (temp 0, schema-constrained), every
quote verified verbatim against its source, keyword fallback when Vertex is down.

ponytail: full-text mode is ONE model call that locates+classifies+compiles (Gemini
reads the whole opinion). The handoff's locate → per-passage classify fan-out +
self-consistency verify on a "red" is the upgrade path if recall/precision on very
long opinions falls short — add it then, not now.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from google.genai import types

from htl.citator.propositions import PROP_IDS, SPINE_TEXT
from htl.llm import vertex
from htl.llm.classify import TYPES, classify_edge
from htl.models.api import CaseRef, TieredEdge
from htl.settings import settings

_HOLDING = ["holding", "dicta"]
_ATTRIBUTION = ["self", "reported"]

# Snippet reads are shallower than a full-opinion read — discount their confidence
# so the lower trust is visible downstream (Feature 4 weights by confidence).
_SNIPPET_CONF = 0.85


@dataclass
class Finding:
    proposition: str | None  # spine id (P1..P8), or None (whole-case)
    treatment: str
    what_changed: str
    holding_vs_dicta: str
    attribution: str
    quote: str
    confidence: float


@dataclass
class EdgeAnalysis:
    analysis_depth: str  # "full-text" | "snippet"
    findings: list[Finding]
    case_summary: str
    model: str


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


# --------------------------------------------------------------------------- #
# Full-text mode (Vertex, primary).                                           #
# --------------------------------------------------------------------------- #
_FT_SYSTEM = (
    "You are a legal citator performing a DEEP read of a full CITING opinion to "
    "decide how it treats a TARGET case (NYSRPA v. Bruen and its progeny) at the "
    "level of individual PROPOSITIONS. Output strictly the JSON schema.\n\n"
    "Read the ENTIRE opinion. Locate every passage that discusses the TARGET — it "
    "may be cited by name across multiple paragraphs, not only where the reporter "
    "citation appears. A single opinion can treat SEVERAL propositions differently "
    "(e.g. follow one, limit another); emit ONE finding per proposition the opinion "
    "actually affects. Merge repeated discussion of the same proposition into a "
    "single strongest finding. If the opinion engages no specific proposition, "
    "return a single whole-case finding with proposition NONE.\n\n"
    "Per finding:\n"
    "- proposition — which of the target's propositions it concerns (or NONE):\n"
    f"{SPINE_TEXT}\n"
    "- treatment — one label: overruled, reversed, abrogated, criticised, "
    "questioned, limited, distinguished, followed, cited-neutral.\n"
    "- what_changed — ONE line: how THIS opinion affects THAT proposition.\n"
    "- holding_vs_dicta — 'holding' if part of the court's binding reasoning, "
    "'dicta' if in passing / hypothetical / background.\n"
    "- attribution — 'self' if THIS opinion is itself doing the treating; 'reported' "
    "if it is merely quoting or describing ANOTHER opinion's treatment. CAUTION: the "
    "phrases 'trapped in amber', 'dead ringer', and 'historical twin' originate in "
    "United States v. Rahimi — a citer OTHER THAN Rahimi using them is REPORTING "
    "Rahimi's treatment (attribution='reported'). Rahimi itself is 'self'.\n"
    "- quote — an EXACT verbatim span copied from the opinion that justifies the "
    "label (no paraphrase).\n"
    "- confidence — your calibrated probability (0..1).\n\n"
    "case_summary — ONE line: the opinion's overall verdict on the target."
)

_FINDING_PROPS = {
    "proposition": {"type": "STRING", "enum": [*PROP_IDS, "NONE"]},
    "treatment": {"type": "STRING", "enum": TYPES},
    "what_changed": {"type": "STRING"},
    "holding_vs_dicta": {"type": "STRING", "enum": _HOLDING},
    "attribution": {"type": "STRING", "enum": _ATTRIBUTION},
    "quote": {"type": "STRING"},
    "confidence": {"type": "NUMBER"},
}
_FT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "case_summary": {"type": "STRING"},
        "findings": {
            "type": "ARRAY",
            "items": {"type": "OBJECT", "properties": _FINDING_PROPS,
                      "required": list(_FINDING_PROPS)},
        },
    },
    "required": ["case_summary", "findings"],
}


def _coerce_finding(d: dict, full_text: str) -> Finding:
    treatment = d.get("treatment") if d.get("treatment") in TYPES else "cited-neutral"
    prop = d.get("proposition")
    prop = prop if prop in PROP_IDS else None  # "NONE"/garbage → None
    hvd = d.get("holding_vs_dicta") if d.get("holding_vs_dicta") in _HOLDING else "dicta"
    attribution = d.get("attribution") if d.get("attribution") in _ATTRIBUTION else "self"
    quote = (d.get("quote") or "").strip()
    if quote and _norm(quote) not in _norm(full_text):  # anti-hallucination
        quote = ""
    try:
        confidence = max(0.0, min(1.0, float(d.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return Finding(prop, treatment, (d.get("what_changed") or "").strip(), hvd,
                   attribution, quote, confidence)


async def _analyze_fulltext_vertex(
    full_text: str, target_name: str | None, target_citation: str | None
) -> EdgeAnalysis:
    target = " ".join(p for p in (target_name, f"({target_citation})" if target_citation else None) if p)
    prompt = (
        f"TARGET case (the cited case): {target or 'unknown'}\n\n"
        f"FULL CITING OPINION:\n\"\"\"\n{full_text}\n\"\"\"\n\n"
        "Deep-read the opinion and report, per proposition, how it treats the TARGET."
    )
    resp = await vertex._get_client().aio.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_FT_SYSTEM,
            response_mime_type="application/json",
            response_schema=_FT_SCHEMA,
            temperature=0.0,
        ),
    )
    data = json.loads(resp.text or "{}")
    findings = [_coerce_finding(d, full_text) for d in (data.get("findings") or [])]
    return EdgeAnalysis("full-text", findings, (data.get("case_summary") or "").strip(),
                        settings.gemini_model)


# --------------------------------------------------------------------------- #
# Snippet mode (reuse Feature 2's edge classifier).                           #
# --------------------------------------------------------------------------- #
def _snippet_line(treatment: str, prop: str | None) -> str:
    where = prop or "the case overall"
    if treatment == "cited-neutral":
        return f"Cited without substantive treatment of {where} (snippet-level read)."
    return f"{treatment.capitalize()} — affects {where} (snippet-level read; full text unavailable)."


async def _analyze_snippet(edge: TieredEdge, case: CaseRef) -> EdgeAnalysis:
    ec = await classify_edge(
        edge.passage, case.case_name, case.citation, edge.signals.propositions_engaged
    )
    finding = Finding(
        proposition=ec.proposition,
        treatment=ec.treatment,
        what_changed=_snippet_line(ec.treatment, ec.proposition),
        holding_vs_dicta=ec.holding_vs_dicta,
        attribution=ec.attribution,
        quote=ec.quote,
        confidence=round(ec.confidence * _SNIPPET_CONF, 3),
    )
    return EdgeAnalysis("snippet", [finding], _snippet_line(ec.treatment, ec.proposition), ec.model)


# --------------------------------------------------------------------------- #
# Public entry point.                                                         #
# --------------------------------------------------------------------------- #
async def analyze_edge(edge: TieredEdge, case: CaseRef, full_text: str | None) -> EdgeAnalysis:
    """Deep-read one edge. Full-text mode when the opinion text is present; snippet
    mode otherwise (or when the full-text read fails — degrade, never pretend)."""
    text = (full_text or "").strip()
    if text:
        try:
            return await _analyze_fulltext_vertex(text, case.case_name, case.citation)
        except Exception:  # vertex down / parse → degrade to the snippet read
            pass
    return await _analyze_snippet(edge, case)
