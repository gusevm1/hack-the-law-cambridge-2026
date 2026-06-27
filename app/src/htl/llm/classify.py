"""Treatment classifier — how does a citing passage treat the case it cites?

Given a citing passage (a snippet of the citing opinion around the citation) and
the target case it cites, return a structured ``Classification``: a treatment
label, its scope, whether it's on other grounds, the exact justifying span, and a
confidence. This is the value layer of the citator (the "is it still good law?"
verdict feeds off these labels).

Primary path is Gemini on Vertex AI (reusing ``llm.vertex``'s ADC client) with
**structured output** (JSON schema) at temperature 0. If the model call fails
(auth, quota, transient), we fall back to a deterministic keyword classifier so
the pipeline always produces a row — the fallback is tagged ``model=
"keyword-fallback"`` so its lower trust is visible downstream.

ponytail: single model tonight. The planned reliability upgrade is an *ensemble*
— run two or three models on Vertex and reconcile (agreement → high confidence,
disagreement → flag for review). One model is enough to demo; leave that for the
hardening pass.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from google.genai import types

from htl.llm import vertex
from htl.settings import settings

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
    resp = await vertex._get_client().aio.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            response_mime_type="application/json",
            response_schema=_SCHEMA,
            temperature=0.0,
        ),
    )
    data = json.loads(resp.text or "{}")

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
        model=settings.gemini_model,
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
