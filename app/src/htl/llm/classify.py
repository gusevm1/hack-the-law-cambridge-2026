"""Treatment classifier — how does a citing passage treat the case it cites?

Given a citing passage (a snippet of the citing opinion around the citation) and
the target case it cites, return a structured ``Classification``: a treatment
label, its scope, whether it's on other grounds, the exact justifying span, and a
confidence. This is the value layer of the citator (the "is it still good law?"
verdict feeds off these labels).

Primary path is Gemini on Vertex AI, routed through ``llm.router`` (task
``"classify"``) with **structured output** (JSON schema) at temperature 0. If the
model call fails (auth, quota, transient), we fall back to a deterministic keyword classifier so
the pipeline always produces a row — the fallback is tagged ``model=
"keyword-fallback"`` so its lower trust is visible downstream.

ponytail: single model tonight. The planned reliability upgrade is an *ensemble*
— run two or three models on Vertex and reconcile (agreement → high confidence,
disagreement → flag for review). One model is enough to demo; leave that for the
hardening pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from htl.citator.propositions import PROP_IDS, SPINE_TEXT
from htl.llm import router

# The treatment vocabulary. Order is severity-ish (most adverse first); the risk
# layer maps these to polarity, this module just emits the label.
TYPES = [
    "overruled",
    "reversed",
    "abrogated",
    "criticised",
    "questioned",
    "limited",
    "distinguished",
    "followed",
    "cited-neutral",
]
SCOPES = ["whole-case", "specific-holding"]


@dataclass
class Classification:
    type: str
    scope: str
    on_other_grounds: bool
    quote: str
    confidence: float
    model: str


# --------------------------------------------------------------------------- #
# Vertex (primary).                                                            #
# --------------------------------------------------------------------------- #
_SYSTEM = (
    "You are a legal citator. You read a passage from a CITING opinion and decide "
    "how it treats the TARGET case it cites. Output strictly the JSON schema.\n"
    "Labels:\n"
    "- overruled: the target (or its holding) is held no longer good law.\n"
    "- reversed: the target judgment is reversed on appeal in the same litigation.\n"
    "- abrogated: superseded/displaced by a later authority or statute.\n"
    "- criticised: disagreed with / called into doubt but not overruled.\n"
    "- questioned: its continued validity is doubted.\n"
    "- limited: confined to its facts / narrowed.\n"
    "- distinguished: held inapplicable to the present facts (NOT negative about the rule).\n"
    "- followed: applied/relied on approvingly.\n"
    "- cited-neutral: merely cited, background, or unclear.\n"
    "Rules: pick the single best label. 'quote' MUST be an exact verbatim span "
    "copied from the passage that justifies the label (no paraphrase). If nothing "
    "in the passage justifies a treatment, use cited-neutral with low confidence. "
    "scope is whole-case unless only a specific holding is treated. confidence is "
    "your calibrated probability the label is correct (0..1)."
)

_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "type": {"type": "STRING", "enum": TYPES},
        "scope": {"type": "STRING", "enum": SCOPES},
        "on_other_grounds": {"type": "BOOLEAN"},
        "quote": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
    },
    "required": ["type", "scope", "on_other_grounds", "quote", "confidence"],
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


async def _classify_vertex(passage: str, target_name: str | None, target_citation: str | None) -> Classification:
    target = " ".join(p for p in (target_name, f"({target_citation})" if target_citation else None) if p)
    prompt = (
        f"TARGET case (the cited case): {target or 'unknown'}\n\n"
        f"PASSAGE from the citing opinion:\n\"\"\"\n{passage}\n\"\"\"\n\n"
        "Classify how the passage treats the TARGET."
    )
    data = await router.complete(
        "classify", system=_SYSTEM, prompt=prompt, schema=_SCHEMA, temperature=0.0
    )

    type_ = data.get("type") if data.get("type") in TYPES else "cited-neutral"
    scope = data.get("scope") if data.get("scope") in SCOPES else "whole-case"
    quote = (data.get("quote") or "").strip()
    # Anti-hallucination: the quote must really be in the passage; drop it if not.
    if quote and _norm(quote) not in _norm(passage):
        quote = ""
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return Classification(
        type=type_,
        scope=scope,
        on_other_grounds=bool(data.get("on_other_grounds", False)),
        quote=quote,
        confidence=confidence,
        model=router.model_for("classify"),
    )


# --------------------------------------------------------------------------- #
# Keyword fallback (deterministic; used only when Vertex is unavailable).      #
# --------------------------------------------------------------------------- #
# Ordered: first match wins. Low confidence — it's a safety net, not the truth.
_KEYWORD_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"overrul", re.I), "overruled"),
    (re.compile(r"abrogat", re.I), "abrogated"),
    (re.compile(r"distinguish", re.I), "distinguished"),
    (re.compile(r"criticis|criticiz", re.I), "criticised"),
    (re.compile(r"question", re.I), "questioned"),
    (re.compile(r"follow", re.I), "followed"),
]


def classify_keyword(passage: str) -> Classification:
    text = passage or ""
    type_ = "cited-neutral"
    quote = ""
    for pattern, label in _KEYWORD_RULES:
        m = pattern.search(text)
        if m:
            type_ = label
            # Quote the sentence the keyword sits in, so the span is verbatim.
            quote = _sentence_around(text, m.start())
            break
    return Classification(
        type=type_,
        scope="whole-case",
        on_other_grounds=False,
        quote=quote,
        confidence=0.4,
        model="keyword-fallback",
    )


def _sentence_around(text: str, idx: int) -> str:
    start = text.rfind(".", 0, idx) + 1
    end = text.find(".", idx)
    end = len(text) if end == -1 else end + 1
    return text[start:end].strip()[:400]


# --------------------------------------------------------------------------- #
# Public entry point.                                                         #
# --------------------------------------------------------------------------- #
async def classify_treatment(
    passage: str, target_name: str | None = None, target_citation: str | None = None
) -> Classification:
    """Classify a citing passage; fall back to keywords if Vertex is unavailable."""
    if not (passage or "").strip():
        return Classification("cited-neutral", "whole-case", False, "", 0.0, "keyword-fallback")
    try:
        return await _classify_vertex(passage, target_name, target_citation)
    except Exception:  # auth/quota/transient/parse → never block the pipeline
        return classify_keyword(passage)


# --------------------------------------------------------------------------- #
# Proposition-level edge classifier (citator pipeline — Feature 2).            #
# --------------------------------------------------------------------------- #
# Same vocabulary + verbatim-quote discipline as above, but emits the *proposition*
# the treatment hits (the spine) and the self-vs-reported attribution — the two
# signals the whole-case ``classify_treatment`` doesn't carry.


@dataclass
class EdgeClass:
    treatment: str
    proposition: str | None  # spine id (P1..P8) the treatment hits, or None
    holding_vs_dicta: str  # "holding" | "dicta"
    attribution: str  # "self" | "reported"
    quote: str  # verbatim span from the passage
    confidence: float
    model: str


_HOLDING = ["holding", "dicta"]
_ATTRIBUTION = ["self", "reported"]

_EDGE_SYSTEM = (
    "You are a legal citator working at the level of individual PROPOSITIONS. You "
    "read a passage from a CITING opinion and decide how it treats the TARGET case "
    "(NYSRPA v. Bruen and its progeny). Output strictly the JSON schema.\n\n"
    "treatment — one label: overruled, reversed, abrogated, criticised, questioned, "
    "limited, distinguished, followed, cited-neutral.\n\n"
    "proposition — which of the target's propositions the treatment concerns. Pick "
    "the single best id, or NONE if the passage treats no specific proposition:\n"
    f"{SPINE_TEXT}\n\n"
    "holding_vs_dicta — 'holding' if the treatment is part of the citing court's "
    "binding reasoning; 'dicta' if it is in passing / hypothetical / background.\n\n"
    "attribution — 'self' if THIS opinion is itself doing the treating; 'reported' "
    "if it is merely quoting or describing ANOTHER opinion's treatment. CAUTION: the "
    "phrases 'trapped in amber', 'dead ringer', and 'historical twin' originate in "
    "United States v. Rahimi — a citer (other than Rahimi) using them is REPORTING "
    "Rahimi's treatment, so attribution='reported'. Rahimi itself is 'self'.\n\n"
    "quote — an EXACT verbatim span copied from the passage that justifies the label "
    "(no paraphrase). If nothing justifies a treatment, use cited-neutral, low "
    "confidence. confidence is your calibrated probability (0..1)."
)

_EDGE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "treatment": {"type": "STRING", "enum": TYPES},
        "proposition": {"type": "STRING", "enum": [*PROP_IDS, "NONE"]},
        "holding_vs_dicta": {"type": "STRING", "enum": _HOLDING},
        "attribution": {"type": "STRING", "enum": _ATTRIBUTION},
        "quote": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
    },
    "required": ["treatment", "proposition", "holding_vs_dicta", "attribution", "quote",
                 "confidence"],
}


async def _classify_edge_vertex(
    passage: str, target_name: str | None, target_citation: str | None
) -> EdgeClass:
    target = " ".join(p for p in (target_name, f"({target_citation})" if target_citation else None) if p)
    prompt = (
        f"TARGET case (the cited case): {target or 'unknown'}\n\n"
        f"PASSAGE from the citing opinion:\n\"\"\"\n{passage}\n\"\"\"\n\n"
        "Classify how the passage treats the TARGET, at the proposition level."
    )
    data = await router.complete(
        "classify", system=_EDGE_SYSTEM, prompt=prompt, schema=_EDGE_SCHEMA, temperature=0.0
    )

    treatment = data.get("treatment") if data.get("treatment") in TYPES else "cited-neutral"
    prop = data.get("proposition")
    prop = prop if prop in PROP_IDS else None  # "NONE"/garbage → None
    hvd = data.get("holding_vs_dicta") if data.get("holding_vs_dicta") in _HOLDING else "dicta"
    attribution = data.get("attribution") if data.get("attribution") in _ATTRIBUTION else "self"
    quote = (data.get("quote") or "").strip()
    if quote and _norm(quote) not in _norm(passage):  # anti-hallucination
        quote = ""
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return EdgeClass(treatment, prop, hvd, attribution, quote, confidence, router.model_for("classify"))


def classify_edge_keyword(passage: str, candidate_propositions: list[str] | None = None) -> EdgeClass:
    """Deterministic safety net: reuse the keyword treatment, and take the
    proposition from the filter's already-computed phrase hits (first one)."""
    base = classify_keyword(passage)
    prop = candidate_propositions[0] if candidate_propositions else None
    return EdgeClass(base.type, prop, "holding", "self", base.quote, 0.4, "keyword-fallback")


async def classify_edge(
    passage: str,
    target_name: str | None = None,
    target_citation: str | None = None,
    candidate_propositions: list[str] | None = None,
) -> EdgeClass:
    """Proposition-level edge classification; keyword fallback if Vertex is down."""
    if not (passage or "").strip():
        return EdgeClass("cited-neutral", None, "dicta", "self", "", 0.0, "keyword-fallback")
    try:
        return await _classify_edge_vertex(passage, target_name, target_citation)
    except Exception:  # auth/quota/transient/parse → never block the pipeline
        return classify_edge_keyword(passage, candidate_propositions)
