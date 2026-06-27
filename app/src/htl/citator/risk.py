"""Risk aggregation — classified treatments → a "still good law?" verdict.

``aggregate_risk`` is a **pure** function (no DB, no network) so it unit-tests
trivially: feed it the case metadata + a list of citing treatments and it returns
the ``RiskResponse``. The route does the DB loading and hands the rows here.

ponytail v1 scoring. The formula is deliberately simple and the thresholds are
**expert-tunable** (a citator's editors would calibrate these against ground
truth) — do not mistake the numbers for settled doctrine:

- Polarity. negative = {overruled, reversed, abrogated, criticised, questioned,
  limited}; positive = {followed}; neutral = {distinguished, cited-neutral}.
  NOTE: ``distinguished`` is genuinely ambiguous — a wall of "distinguished" can
  signal a court boxing a precedent in. v1 treats it as neutral; an editor may
  want it as mild-negative.
- Court weight (of the *citing* court): scotus 1.0, federal circuit 0.6, else 0.3.
- A strong negative (overruled/reversed/abrogated) at confidence ≥ 0.6 from a
  high court (scotus or circuit) is dispositive → red / score 1.0. Otherwise the
  score is the court-&-recency-weighted negative share of the assessed treatments
  plus a small bonus when the negative trend is rising.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from htl.models.api import (
    CaseRef,
    CitingCaseRef,
    GroundTruth,
    NegativeTreatment,
    PositiveSignal,
    RiskResponse,
    TrendPoint,
)

NEGATIVE = {"overruled", "reversed", "abrogated", "criticised", "questioned", "limited"}
POSITIVE = {"followed"}
STRONG_NEGATIVE = {"overruled", "reversed", "abrogated"}
# distinguished / cited-neutral → neutral (no polarity).


def polarity_label(type_: str | None) -> str:
    """Display polarity of a treatment type: 'negative' | 'positive' | 'neutral'.
    The string mirror of ``_polarity`` (int), shared by /graph and the analyze gate
    so 'neutral' means the same thing everywhere (distinguished + cited-neutral +
    unclassified all read neutral)."""
    if type_ in NEGATIVE:
        return "negative"
    if type_ in POSITIVE:
        return "positive"
    return "neutral"

_FED_CIRCUIT = re.compile(r"^(ca\d+|cadc|cafc)$")

# Thresholds (expert-tunable).
_STRONG_CONF = 0.6  # confidence floor for a dispositive strong-negative
_HIGH_COURT = 0.6  # court-weight floor counting as a "high court"
_AMBER_FLOOR = 0.4  # risk_score above this (but not red) → amber

# Curated stub of the Library of Congress "Table of Decisions Overruled" for our
# four seeded targets. The full table is large; this is the demo slice. Keyed by
# CourtListener cluster id (== cl_opinions.id == case_id).
GROUND_TRUTH: dict[int, str] = {
    108713: "Dobbs v. Jackson (2022)",  # Roe v. Wade
    94508: "Brown v. Board (1954)",  # Plessy v. Ferguson
    111738: "Lawrence v. Texas (2003)",  # Bowers v. Hardwick
    96276: "West Coast Hotel (1937)",  # Lochner v. New York
}


@dataclass
class CitingTreatment:
    """A classified treatment joined with its citing case's metadata."""

    type: str
    scope: str | None
    on_other_grounds: bool
    quote: str | None
    confidence: float | None
    citing_case_name: str | None
    citing_court: str | None
    citing_date_filed: date | None


def court_weight(court: str | None) -> float:
    if court == "scotus":
        return 1.0
    if court and _FED_CIRCUIT.match(court):
        return 0.6
    return 0.3


def _polarity(type_: str) -> int:
    if type_ in NEGATIVE:
        return -1
    if type_ in POSITIVE:
        return 1
    return 0


def _recency_factor(year: int | None, today_year: int) -> float:
    """Recent treatments weigh more; floor at 0.4 so old law still counts."""
    if year is None:
        return 0.6
    age = max(0, today_year - year)
    return max(0.4, 1.0 - age / 60.0)


def _conf(t: CitingTreatment) -> float:
    return t.confidence if t.confidence is not None else 1.0


def _build_trend(treatments: list[CitingTreatment]) -> list[TrendPoint]:
    """Group signal-bearing (neg/pos) treatments by citing year — the erosion curve."""
    by_year: dict[int, list[int]] = {}  # year -> [neg, pos]
    for t in treatments:
        pol = _polarity(t.type)
        if pol == 0 or t.citing_date_filed is None:
            continue
        bucket = by_year.setdefault(t.citing_date_filed.year, [0, 0])
        bucket[0 if pol < 0 else 1] += 1
    points = []
    for year in sorted(by_year):
        neg, pos = by_year[year]
        total = neg + pos
        points.append(TrendPoint(year=year, neg=neg, pos=pos, neg_share=neg / total if total else 0.0))
    return points


def _severity(t: CitingTreatment) -> tuple[int, float]:
    """Sort key for negative treatments: strongest + highest-court + most-confident first."""
    strong = 1 if t.type in STRONG_NEGATIVE else 0
    return (strong, court_weight(t.citing_court) * _conf(t))


def aggregate_risk(
    case: dict, treatments: list[CitingTreatment], *, total_citing: int, today: date
) -> RiskResponse:
    case_id = case["case_id"]
    gt_by = GROUND_TRUTH.get(case_id)
    ground_truth = GroundTruth(on_loc_overruled_list=gt_by is not None, overruled_by=gt_by)
    case_ref = CaseRef(
        case_id=case_id,
        case_name=case.get("case_name"),
        citation=case.get("citation"),
        court=case.get("court"),
        date_filed=case["date_filed"].isoformat() if case.get("date_filed") else None,
    )
    base = dict(case=case_ref, as_of=today.isoformat(), trend=[], ground_truth=ground_truth)

    if not treatments:
        return RiskResponse(
            **base,
            signal="unknown",
            status="unknown",
            risk_score=0.0,
            risk_rationale="No citing treatments on record yet.",
            negative_treatments=[],
            positive_signal=PositiveSignal(approving_cites=0, total_citing=total_citing),
        )

    trend = _build_trend(treatments)
    negatives = sorted((t for t in treatments if _polarity(t.type) < 0), key=_severity, reverse=True)
    approving = sum(1 for t in treatments if t.type in POSITIVE)
    neg_models = [
        NegativeTreatment(
            citing_case=CitingCaseRef(
                case_name=t.citing_case_name,
                court=t.citing_court,
                date_filed=t.citing_date_filed.isoformat() if t.citing_date_filed else None,
            ),
            type=t.type,
            scope=t.scope,
            on_other_grounds=bool(t.on_other_grounds),
            quote=t.quote,
            confidence=t.confidence,
        )
        for t in negatives
    ]
    positive_signal = PositiveSignal(approving_cites=approving, total_citing=total_citing)

    # --- dispositive strong-negative from a high court → red ---------------- #
    dispositive = next(
        (
            t
            for t in negatives
            if t.type in STRONG_NEGATIVE
            and _conf(t) >= _STRONG_CONF
            and court_weight(t.citing_court) >= _HIGH_COURT
        ),
        None,
    )
    if dispositive is not None:
        if gt_by:
            rationale = f"No longer good law — overruled by {gt_by}."
        else:
            who = dispositive.citing_case_name or "a high court"
            yr = dispositive.citing_date_filed.year if dispositive.citing_date_filed else "?"
            rationale = f"{dispositive.type.capitalize()} by {who} ({dispositive.citing_court}, {yr})."
        return RiskResponse(
            **{**base, "trend": trend},
            signal="red",
            status="overruled",
            risk_score=1.0,
            risk_rationale=rationale,
            negative_treatments=neg_models,
            positive_signal=positive_signal,
        )

    # --- graded score: weighted negative share (+ rising-trend bonus) ------- #
    today_year = today.year
    neg_w = total_w = 0.0
    for t in treatments:
        w = court_weight(t.citing_court) * _conf(t) * _recency_factor(
            t.citing_date_filed.year if t.citing_date_filed else None, today_year
        )
        total_w += w
        if _polarity(t.type) < 0:
            neg_w += w
    neg_share = neg_w / total_w if total_w else 0.0

    shares = [(p.year, p.neg_share) for p in trend if p.neg + p.pos > 0]
    rising = len(shares) >= 2 and shares[-1][1] > shares[0][1]
    trend_bonus = 0.1 if rising else 0.0

    risk_score = max(0.0, min(1.0, neg_share + trend_bonus))
    if risk_score > _AMBER_FLOOR:
        signal, status = "amber", "good-but-eroding"
        rationale = (
            f"{len(negatives)} negative treatment(s); weighted negative share "
            f"{neg_share:.0%}{', rising' if rising else ''}."
        )
    else:
        signal, status = "green", "good"
        rationale = (
            f"Predominantly neutral/approving across {len(treatments)} assessed "
            f"citation(s)." if treatments else "No adverse treatment on record."
        )
    return RiskResponse(
        **{**base, "trend": trend},
        signal=signal,
        status=status,
        risk_score=round(risk_score, 3),
        risk_rationale=rationale,
        negative_treatments=neg_models,
        positive_signal=positive_signal,
    )
