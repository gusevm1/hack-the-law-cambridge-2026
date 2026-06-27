"""Contract-B mock — per-proposition verdicts for the use-aware stage to consume.

Feature 4 (B) builds the real ``GET /cases/{id}/propositions``; until it lands, the
verdict stage (C) reads this contract-true stub so it can be built and demoed
end-to-end. Mirrors the Bruen golden end-state (scope §5): public-carry intact,
methodology good, the rigid history-twin reading and sensitive places eroded, the
§922(g) "people" question split. Swap ``PROPOSITIONS[id]`` for B's response on wire.
"""

from __future__ import annotations

from datetime import date

from htl.citator.golden import BRUEN_ID, _CASE
from htl.models.api import (
    CircuitSplit,
    CloseToOverruled,
    PropositionsResponse,
    PropositionVerdict,
)

_NOT_CLOSE = CloseToOverruled(flag=False, confidence=0.9, rationale="Not close to overruled.")

_BRUEN_PROPS = [
    PropositionVerdict(
        proposition_id="P1", label="Public-carry right",
        summary="Right to carry in public for self-defense; may-issue 'proper cause' struck.",
        signal="green", status="good", risk_score=0.1,
        what_changed="Reaffirmed and applied; no binding negative treatment.",
        close_to_overruled=_NOT_CLOSE,
        supporting_edges=["Antonyuk v. James"],
    ),
    PropositionVerdict(
        proposition_id="P2", label="Text-history-tradition",
        summary="Gun laws judged by historical tradition; means-end scrutiny rejected.",
        signal="green", status="good", risk_score=0.15,
        what_changed="Reaffirmed — Rahimi expressly follows the methodology.",
        close_to_overruled=_NOT_CLOSE,
        supporting_edges=["United States v. Rahimi"],
    ),
    PropositionVerdict(
        proposition_id="P2a", label="Analogue not twin",
        summary="Historical analogue need only be 'relevantly similar', not a twin.",
        signal="amber", status="limited", risk_score=0.55,
        what_changed=(
            "Rahimi (2024) rejected the rigid 'dead ringer / historical twin' reading "
            "as a misunderstanding of the methodology — analogues need only be "
            "'relevantly similar' on how and why they burden the right."
        ),
        close_to_overruled=_NOT_CLOSE,
        supporting_edges=["United States v. Rahimi"],
    ),
    PropositionVerdict(
        proposition_id="P3", label="Sensitive places",
        summary="'Sensitive places' may bar carry, but the category was left undefined.",
        signal="amber", status="good-but-eroding", risk_score=0.5,
        what_changed=(
            "Contested and expanding — circuits split on how far the undefined category "
            "reaches (Wolford partly upheld Hawaii's designations, struck the "
            "private-property default)."
        ),
        circuit_split=CircuitSplit(
            present=True, follows=["ca9"], limits=["ca2"],
            summary="Circuits diverge on the scope of permissible sensitive-place bans.",
        ),
        close_to_overruled=_NOT_CLOSE,
        supporting_edges=["Wolford v. Lopez", "Antonyuk v. James"],
    ),
    PropositionVerdict(
        proposition_id="P5", label="The people / §922(g)",
        summary="Who counts among 'the people' and may be disarmed (felons, DV, §922(g)).",
        signal="amber", status="good-but-eroding", risk_score=0.6,
        what_changed=(
            "The hottest split — categorical vs as-applied disarmament. Rahimi limited "
            "Bruen's 'responsible' framing (a vague standard), grounding disarmament in "
            "dangerousness instead."
        ),
        circuit_split=CircuitSplit(
            present=True, follows=["ca8"], limits=["ca3"],
            summary="Circuits split on categorical §922(g) bars vs as-applied for the non-dangerous.",
        ),
        close_to_overruled=_NOT_CLOSE,
        supporting_edges=["United States v. Jackson", "Range v. Attorney General"],
    ),
]

_BRUEN = PropositionsResponse(
    case=_CASE,
    operative_rule="Good law as modified by United States v. Rahimi (2024).",
    propositions=_BRUEN_PROPS,
    as_of=date(2026, 6, 27).isoformat(),
)

# Keyed by CL cluster id (== /resolve's case_id), like golden.CITATIONS.
PROPOSITIONS: dict[int, PropositionsResponse] = {BRUEN_ID: _BRUEN}


def propositions_for(case_id: int, *, today: date) -> PropositionsResponse:
    """The per-proposition verdicts for a case, or an empty contract-true response
    (so the verdict stage degrades gracefully for not-yet-analysed cases)."""
    hit = PROPOSITIONS.get(case_id)
    if hit is not None:
        return hit
    from htl.models.api import CaseRef

    return PropositionsResponse(
        case=CaseRef(case_id=case_id),
        operative_rule="No proposition-level analysis available yet.",
        propositions=[],
        as_of=today.isoformat(),
    )
