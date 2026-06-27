"""Triage / filter — tier inbound citation edges by *depth of analysis*.

``tier_edges`` is a **pure** function (no DB, no network) mirroring
``risk.aggregate_risk``: feed it the target case + raw ``Edge``s and it returns a
``TriageResponse`` with every edge tagged ``deep | shallow | mention``. It is the
cheap, deterministic, auditable front of the pipeline: decide *how much* (expensive,
later) analysis each edge earns. It **NEVER drops** — noise is surfaced as
``mention``, low-ranked, never hidden (hiding is worse than mentioning).

ponytail v1 — keyword/metadata only, no LLM. Tier from four signals:

  score = binding-court × treatment-keyword × proposition-phrase × recency

with hard overrides on top (noise → ``mention``; an apex binding treatment such
as Rahimi → force ``deep``). Phrase tables are §4 of the citator scope doc
(lawyer-confirmed). Thresholds are expert-tunable — don't read the numbers as
doctrine.
"""

from __future__ import annotations

import re
from datetime import date

from htl.citator import courts
from htl.citator.propositions import PHRASES as PROPOSITION_PHRASES
from htl.models.api import (
    CaseRef,
    Edge,
    TieredEdge,
    TriageCounts,
    TriageResponse,
    TriageSignals,
)

# --- Signal vocab (deterministic) ------------------------------------------- #
# Proposition spine (§4 lawyer-confirmed signal phrases) lives in
# ``citator.propositions``. An edge "engages" a proposition when its passage
# contains one of its phrases (substring, hyphen-normalised — see ``_norm``).

# Treatment language. "Strong" = substantive negative/limiting engagement that, from
# a binding court, earns deep analysis. The rest still count as treatment, weaker.
STRONG_TREATMENT = {
    "overruled", "abrogated", "reversed", "vacated", "limited", "narrowed",
    "clarified", "misunderstood", "modified", "declined to extend",
    "called into question", "abrogating", "overruling",
}
OTHER_TREATMENT = {
    "followed", "following", "applying", "applied", "reaffirmed", "reaffirming",
    "adopted", "relied on", "relies on", "distinguished", "distinguishing",
}
TREATMENT_KEYWORDS = STRONG_TREATMENT | OTHER_TREATMENT

_PROCEDURAL = "by operation of law"  # "overruled by operation of law" = a docket event

# Court binding tier lives in citator.courts (shared with retrieval ingest).
_DEEP_SCORE = 0.40  # score at/above this (and binding) → deep


def _target_tokens(case_name: str | None) -> list[str]:
    """Distinctive name tokens for reversed-direction detection. The party after
    the last 'v.' is the short name lawyers cite by (Bruen, Heller)."""
    if not case_name:
        return []
    tail = re.split(r"\bv\.?\b", case_name)[-1]
    toks = re.findall(r"[A-Za-z]{4,}", tail.lower())
    stop = {"city", "county", "state", "united", "states", "department", "commissioner"}
    return [t for t in toks if t not in stop]


def _norm(s: str) -> str:
    """Lower-case and collapse hyphens to spaces so 'sensitive-place' matches
    'sensitive place' and 'may-issue' matches 'may issue' — real passages vary."""
    return s.lower().replace("-", " ")


def _matched(passage: str, vocab) -> list[str]:
    p = _norm(passage)
    return [kw for kw in vocab if _norm(kw) in p]


def _propositions(passage: str) -> list[str]:
    p = _norm(passage)
    return [pid for pid, phrases in PROPOSITION_PHRASES.items()
            if any(_norm(ph) in p for ph in phrases)]


def _recency_factor(years: int) -> float:
    """Recent treatments weigh more; floor 0.4 so old-but-on-point still counts."""
    return max(0.4, 1.0 - max(0, years) / 60.0)


def _reversed_direction(passage: str, target_tokens: list[str]) -> bool:
    """The target is the OVERRULER here, not the overruled — e.g. '… overruled by
    Bruen'. Such an edge is noise for *the target's* good-law question."""
    if not target_tokens:
        return False
    p = passage.lower()
    pat = r"overrul\w*\s+by\b[^.;]{0,40}\b(" + "|".join(map(re.escape, target_tokens)) + r")\b"
    return re.search(pat, p) is not None


def _tier_one(edge: Edge, target_tokens: list[str], today: date) -> TieredEdge:
    passage = edge.passage or ""
    court = edge.citing_case.court
    binding, binding_w = courts.binding(court)
    treatment_kw = _matched(passage, TREATMENT_KEYWORDS)
    strong_kw = _matched(passage, STRONG_TREATMENT)
    props = _propositions(passage)

    year = int(edge.citing_case.date_filed[:4]) if edge.citing_case.date_filed else None
    recency_years = (today.year - year) if year is not None else today.year
    signals = TriageSignals(
        binding=binding,
        treatment_kw=treatment_kw,
        propositions_engaged=props,
        recency_years=recency_years,
    )

    reasons: list[str] = []

    # --- hard overrides: noise is always surfaced, never dropped → mention --- #
    if _PROCEDURAL in passage.lower():
        reasons.append("procedural: 'by operation of law' is a docket event, not a "
                       "treatment of the target")
        return TieredEdge(**edge.model_dump(), tier="mention", reasons=reasons, signals=signals)
    if _reversed_direction(passage, target_tokens):
        reasons.append("reversed-direction: the target is the overruler here, not the "
                       "case being overruled")
        return TieredEdge(**edge.model_dump(), tier="mention", reasons=reasons, signals=signals)
    if not treatment_kw and not props:
        reasons.append("bare cite: no treatment language or proposition engagement detected")
        return TieredEdge(**edge.model_dump(), tier="mention", reasons=reasons, signals=signals)

    # --- apex binding treatment (e.g. Rahimi) → force deep ------------------- #
    if court == "scotus" and strong_kw and props:
        reasons.append(f"apex binding treatment: SCOTUS {strong_kw[0]} engaging "
                       f"{', '.join(props)}")
        return TieredEdge(**edge.model_dump(), tier="deep", reasons=reasons, signals=signals)

    # --- graded score: binding × treatment × proposition × recency ---------- #
    treat_w = 1.0 if strong_kw else (0.6 if treatment_kw else 0.3)
    prop_w = 1.0 if len(props) >= 2 else (0.7 if props else 0.3)
    score = binding_w * treat_w * prop_w * _recency_factor(recency_years)

    if binding:
        reasons.append(f"binding court ({court})")
    if strong_kw:
        reasons.append(f"strong treatment: {', '.join(strong_kw)}")
    elif treatment_kw:
        reasons.append(f"treatment: {', '.join(treatment_kw)}")
    if props:
        reasons.append(f"engages {', '.join(props)}")
    reasons.append(f"score {score:.2f}")

    tier = "deep" if (binding and score >= _DEEP_SCORE) else "shallow"
    return TieredEdge(**edge.model_dump(), tier=tier, reasons=reasons, signals=signals)


def tier_edges(case: CaseRef, edges: list[Edge], *, today: date) -> TriageResponse:
    target_tokens = _target_tokens(case.case_name)
    tiered = [_tier_one(e, target_tokens, today) for e in edges]
    counts = TriageCounts(
        deep=sum(1 for e in tiered if e.tier == "deep"),
        shallow=sum(1 for e in tiered if e.tier == "shallow"),
        mention=sum(1 for e in tiered if e.tier == "mention"),
    )
    # deep first, then shallow, then mention — the funnel, ordered.
    order = {"deep": 0, "shallow": 1, "mention": 2}
    tiered.sort(key=lambda e: order[e.tier])
    return TriageResponse(case=case, total=len(tiered), counts=counts, edges=tiered)
