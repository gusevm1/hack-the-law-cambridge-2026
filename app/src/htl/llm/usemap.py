"""Map a lawyer's intended USE of a case to the propositions it depends on.

The dropdown is **proposition-aligned** (decision 1a): each option carries its
default proposition id(s), so the common path is purely deterministic — no model
call. The free-form ``intent`` (and any off-menu use) is where the LLM earns its
keep: it maps the nuance onto the spine, schema-constrained to ``PROP_IDS``.

Mirrors ``llm.classify``: Vertex (temp 0, schema-constrained) with a deterministic
fallback — here the fallback is the dropdown's own default ids, so a use picked
from the menu always resolves even when Vertex is unavailable.
"""

from __future__ import annotations

import json

from google.genai import types

from htl.citator.propositions import PROP_IDS, SPINE_TEXT
from htl.llm import vertex
from htl.models.api import UseMapping
from htl.settings import settings

# Proposition-aligned dropdown → default proposition id(s). These labels are the
# canonical use options; the frontend dropdown mirrors them verbatim (ponytail:
# 6 stable strings duplicated FE-side rather than served from an endpoint).
USE_DEFAULTS: dict[str, list[str]] = {
    "Public-carry right (P1)": ["P1"],
    "History-and-tradition test (P2/P2a)": ["P2", "P2a"],
    "Sensitive-places restriction (P3)": ["P3"],
    "Assault-weapon / magazine ban (P4)": ["P4"],
    "Felon / §922(g) disqualification (P5)": ["P5"],
    "Licensing regime (P7)": ["P7"],
}


_SYSTEM = (
    "You map a litigator's intended USE of a court case to the case's PROPOSITIONS "
    "— the specific holdings/principles the use depends on. The target is NYSRPA v. "
    "Bruen and its progeny (gun law). Output strictly the JSON schema.\n\n"
    "Pick every proposition id the described use actually relies on (often one, "
    "sometimes two). Use the spine:\n"
    f"{SPINE_TEXT}\n\n"
    "engaged_propositions — the ids the use depends on (subset of the spine). "
    "rationale — one line tying the use to those propositions. If the use is generic "
    "(e.g. 'cite as persuasive authority') map to the proposition(s) the case is "
    "actually being cited for, given the provided default hint."
)

_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "engaged_propositions": {"type": "ARRAY", "items": {"type": "STRING", "enum": PROP_IDS}},
        "rationale": {"type": "STRING"},
    },
    "required": ["engaged_propositions", "rationale"],
}


def _dedupe(ids: list[str]) -> list[str]:
    seen: list[str] = []
    for i in ids:
        if i in PROP_IDS and i not in seen:
            seen.append(i)
    return seen


async def _map_vertex(use: str, intent: str, defaults: list[str]) -> tuple[list[str], str]:
    prompt = (
        f"USE (selected): {use or 'unspecified'}\n"
        f"How they intend to use it (free-form): {intent or '(none given)'}\n"
        f"Default proposition hint for this use: {', '.join(defaults) or '(none)'}\n\n"
        "Which propositions does this use depend on?"
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
    ids = _dedupe(data.get("engaged_propositions") or [])
    rationale = (data.get("rationale") or "").strip() or "Mapped by the model from the stated use."
    return ids, rationale


async def map_use_to_propositions(use: str, intent: str = "") -> UseMapping:
    """Resolve a use (+ optional free-form intent) to engaged proposition ids."""
    use = (use or "").strip()
    intent = (intent or "").strip()
    defaults = USE_DEFAULTS.get(use, [])

    # Common path: a known dropdown use with no free-form refinement → deterministic,
    # no model call (the dropdown IS proposition-aligned).
    if defaults and not intent:
        return UseMapping(
            use_label=use, intent=intent, engaged_propositions=defaults,
            rationale="Mapped from the selected use.",
        )

    try:
        ids, rationale = await _map_vertex(use, intent, defaults)
        # Keep the deterministic defaults if the model returned nothing usable.
        if ids:
            return UseMapping(use_label=use, intent=intent, engaged_propositions=ids, rationale=rationale)
    except Exception:  # auth/quota/transient/parse → fall back to the default ids
        pass

    if defaults:
        return UseMapping(
            use_label=use, intent=intent, engaged_propositions=defaults,
            rationale="Mapped from the selected use (model unavailable; used the default).",
        )
    return UseMapping(
        use_label=use, intent=intent, engaged_propositions=[],
        rationale="Couldn't map this use to a specific proposition — review manually.",
    )
