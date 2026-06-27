"""Use-aware verdict — Feature 5 (C), the payoff stage of the citator.

Risk **relative to the lawyer's intended use**, not the case as a whole. A case can
be perfectly good law for one proposition and eroded on another; whether that
erosion is *real risk* depends entirely on which proposition the lawyer leans on.

``compose_verdict`` is a **pure** function (no DB, no network, no LLM) so it unit-
tests trivially: feed it the per-proposition verdicts (Contract B) + the resolved
use→proposition mapping and it returns the ``VerdictResponse``. The one impure part
— mapping a free-form use to proposition ids — lives in ``llm.usemap`` and is done
*before* this; here we only intersect and explain.

Real risk = (propositions the use engages) ∩ (propositions that are compromised,
i.e. signal amber/red). Computed in code, never asserted by the model.
"""

from __future__ import annotations

from htl.models.api import (
    CloseToOverruled,
    PropositionsResponse,
    UseMapping,
    UseProposition,
    VerdictResponse,
)

# A proposition is "compromised" when its good-law signal is amber or red. green /
# unknown do not count as risk (unknown is surfaced as needs-review elsewhere).
COMPROMISED = {"amber", "red"}


def _note(relevant: bool, p) -> str:
    """One line on what this proposition means *for this use*."""
    if not relevant:
        return f"Not engaged by your use (currently {p.signal})."
    if p.signal == "red":
        return f"Relied on by your use and {p.status} — {p.what_changed}"
    if p.signal == "amber":
        return f"Relied on by your use; {p.what_changed}"
    if p.signal == "green":
        return "Relied on by your use and currently good law."
    return "Relied on by your use; status unclear — needs review."


def _close_to_overruled(engaged_props) -> CloseToOverruled:
    """Aggregate close-to-overruled across the propositions the use engages.

    Surface the worst engaged signal; abstain ("needs review") on a conflict. Code-
    grounded only — we never let a model assert this (the malpractice boundary)."""
    if not engaged_props:
        return CloseToOverruled(
            flag=False, confidence=0.0,
            rationale="No proposition mapped for this use.",
        )
    flagged = [p.close_to_overruled for p in engaged_props
               if p.close_to_overruled and p.close_to_overruled.flag]
    if flagged:
        return max(flagged, key=lambda c: c.confidence)
    review = [p.close_to_overruled for p in engaged_props
              if p.close_to_overruled and "needs review" in (p.close_to_overruled.rationale or "").lower()]
    if review:
        return CloseToOverruled(
            flag=False, confidence=review[0].confidence,
            rationale="needs review — conflicting signals on an engaged proposition",
        )
    return CloseToOverruled(
        flag=False, confidence=0.9,
        rationale="No engaged proposition is close to being overruled.",
    )


def _final_labels(props: PropositionsResponse, cto: CloseToOverruled) -> list[str]:
    """The composed badges: operative rule + structural signals + close-to-overruled."""
    labels: list[str] = [props.operative_rule]
    for p in props.propositions:
        if p.circuit_split and p.circuit_split.present:
            labels.append(f"circuit split on {p.proposition_id}")
        if p.cert and p.cert.granted:
            labels.append(f"cert pending on {p.proposition_id}")
    labels.append(f"close to overruled: {'yes' if cto.flag else 'no'}")
    return labels


def compose_verdict(props: PropositionsResponse, mapping: UseMapping) -> VerdictResponse:
    """Intersect the use's engaged propositions with the compromised ones and explain.

    Everything is keyed to the propositions the case-analysis (Contract B) actually
    carries; an engaged id with no analysis for this case can't be a real risk (it's
    surfaced as needs-review instead of a false all-clear)."""
    engaged = set(mapping.engaged_propositions)
    # Spine-ordered for stable explanation text. "_present" = analysed for this case.
    engaged_present = [p for p in props.propositions if p.proposition_id in engaged]
    hit = [p for p in engaged_present if p.signal in COMPROMISED]
    real_risk = bool(hit)

    per_proposition = [
        UseProposition(
            proposition_id=p.proposition_id,
            signal=p.signal,
            relevant_to_use=p.proposition_id in engaged,
            note=_note(p.proposition_id in engaged, p),
        )
        for p in props.propositions
    ]

    if real_risk:
        parts = [f"{p.label} ({p.signal}): {p.what_changed}" for p in hit]
        risk_explanation = "Real risk for this use — it depends on " + "; ".join(parts)
    elif not engaged:
        risk_explanation = (
            "Couldn't map your use to a specific proposition of this case — review "
            "the per-proposition signals manually before relying on it."
        )
    elif not engaged_present:
        risk_explanation = (
            f"Your use depends on {', '.join(sorted(engaged))}, which isn't among the "
            "propositions analysed for this case yet — review manually."
        )
    else:
        engaged_labels = [p.label for p in engaged_present]
        verb = "remains" if len(engaged_present) == 1 else "remain"
        eroded_elsewhere = [p.label for p in props.propositions
                            if p.signal in COMPROMISED and p.proposition_id not in engaged]
        if eroded_elsewhere:
            risk_explanation = (
                f"Safe for this use. It rests on {', '.join(engaged_labels)}, which "
                f"{verb} good law; the erosion on {', '.join(eroded_elsewhere)} doesn't "
                "touch it."
            )
        else:
            risk_explanation = (
                f"Safe for this use. It rests on {', '.join(engaged_labels)}; no "
                "compromised proposition among those it engages."
            )

    cto = _close_to_overruled(engaged_present)
    return VerdictResponse(
        case=props.case,
        operative_rule=props.operative_rule,
        use=mapping,
        real_risk=real_risk,
        risk_explanation=risk_explanation,
        per_proposition=per_proposition,
        final_labels=_final_labels(props, cto),
        close_to_overruled=cto,
        as_of=props.as_of,
    )
