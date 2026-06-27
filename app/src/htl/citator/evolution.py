"""Proposition evolution + risk + trajectory (Feature 4 / B).

The aggregation stage: turn per-case findings (Contract A — the deep analyzer's
``AnalyzedEdge.findings``) into a per-*proposition* verdict. Mirrors the discipline
of ``risk.aggregate_risk`` — ``aggregate_propositions`` is a **pure** function (no
DB, no network, no LLM), so it unit-tests trivially with synthetic findings.

Per proposition it computes, deterministically:

- **risk_score + signal** — reuses ``risk.py`` helpers (``court_weight``,
  ``_recency_factor``, the dispositive-strong-negative rule). Code, never the model.
- **circuit_split** — group the proposition's *self* findings by federal circuit;
  divergent polarity across circuits ⇒ ``present=True`` (e.g. P5: CA8 follows §922(g)
  vs CA3 limits it as-applied).
- **timeline** — chronological treatments with a polarity per point.
- **what_changed** — a grounded narrative composed *only* from the findings (each
  clause restates a verified finding), so there is nothing to hallucinate.
- **close_to_overruled** — trajectory synthesis that **abstains** ("needs review")
  when signals conflict. The malpractice boundary: never a confident wrong answer.
- **cert** — injected from the curated cert-watch table (``certwatch.py``); this
  module never asserts a cert grant itself.

Attribution trap (scope §4): a "reported" finding is a citer *echoing* another
opinion's treatment (e.g. quoting Rahimi's "trapped in amber"). It must not be
scored as that citer's own treatment, so reported findings carry polarity 0 here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from htl.citator.propositions import PROP_IDS, PROPOSITIONS
from htl.citator.risk import (
    _AMBER_FLOOR,
    _FED_CIRCUIT,
    _HIGH_COURT,
    _STRONG_CONF,
    NEGATIVE,
    POSITIVE,
    STRONG_NEGATIVE,
    _recency_factor,
    court_weight,
)
from htl.models.api import (
    AnalyzedEdge,
    CaseRef,
    CertStatus,
    CircuitSplit,
    CloseToOverruled,
    PropositionsResponse,
    PropositionVerdict,
    TimelinePoint,
)

SOFT_NEGATIVE = NEGATIVE - STRONG_NEGATIVE  # criticised / questioned / limited

_LABELS = {p.id: (p.label, p.summary) for p in PROPOSITIONS}
_ORDER = {pid: i for i, pid in enumerate(PROP_IDS)}


@dataclass
class PropFinding:
    """A ``PropositionFinding`` flattened with its citing case's metadata — the unit
    of aggregation (one case can yield several, one per proposition it touches)."""

    proposition: str | None
    treatment: str
    what_changed: str
    attribution: str  # "self" | "reported"
    holding_vs_dicta: str
    quote: str
    confidence: float
    citing_case_name: str | None
    citing_court: str | None
    citing_year: int | None


def findings_from_edges(edges: list[AnalyzedEdge]) -> list[PropFinding]:
    """Flatten analyzed edges into joined findings (the route's adapter)."""
    out: list[PropFinding] = []
    for e in edges:
        cc = e.citing_case
        year = int(cc.date_filed[:4]) if cc.date_filed else None
        for f in e.findings:
            out.append(
                PropFinding(
                    proposition=f.proposition,
                    treatment=f.treatment,
                    what_changed=f.what_changed,
                    attribution=f.attribution,
                    holding_vs_dicta=f.holding_vs_dicta,
                    quote=f.quote,
                    confidence=f.confidence,
                    citing_case_name=cc.case_name,
                    citing_court=cc.court,
                    citing_year=year,
                )
            )
    return out


# --- polarity / severity ---------------------------------------------------- #
def _polarity(treatment: str) -> int:
    if treatment in NEGATIVE:
        return -1
    if treatment in POSITIVE:
        return 1
    return 0


def _severity(treatment: str) -> float:
    """Negativity weight: a strong negative bites fully, a soft one (limited /
    criticised / questioned) partially, everything else not at all."""
    if treatment in STRONG_NEGATIVE:
        return 1.0
    if treatment in SOFT_NEGATIVE:
        return 0.6
    return 0.0


def _scored(findings: list[PropFinding]) -> list[PropFinding]:
    """Only 'self' findings drive risk — a reported echo isn't the citer's own act."""
    return [f for f in findings if f.attribution == "self"]


def _conf(f: PropFinding) -> float:
    return f.confidence if f.confidence is not None else 1.0


def _is_fed_circuit(court: str | None) -> bool:
    return bool(court and _FED_CIRCUIT.match(court))


# --- circuit split (derived, deterministic) --------------------------------- #
def _circuit_split(findings: list[PropFinding]) -> CircuitSplit | None:
    by_circuit: dict[str, int] = {}
    for f in _scored(findings):
        if not _is_fed_circuit(f.citing_court):
            continue
        by_circuit[f.citing_court] = by_circuit.get(f.citing_court, 0) + _polarity(f.treatment)
    follows = sorted(c for c, v in by_circuit.items() if v > 0)
    limits = sorted(c for c, v in by_circuit.items() if v < 0)
    present = bool(follows) and bool(limits)
    if not present:
        return None  # no divergence among circuits → no split to report
    summary = (
        f"Federal circuits diverge: {', '.join(follows)} apply/uphold the target; "
        f"{', '.join(limits)} cut against it."
    )
    return CircuitSplit(present=True, follows=follows, limits=limits, summary=summary)


# --- per-proposition risk (mirrors risk.aggregate_risk) --------------------- #
def _dispositive(findings: list[PropFinding]) -> PropFinding | None:
    """A strong negative (overruled/reversed/abrogated), self-attributed, from a
    high court at confidence ≥ floor → dispositive red (same rule as risk.py)."""
    return next(
        (
            f
            for f in _scored(findings)
            if f.treatment in STRONG_NEGATIVE
            and _conf(f) >= _STRONG_CONF
            and court_weight(f.citing_court) >= _HIGH_COURT
        ),
        None,
    )


def _risk(
    findings: list[PropFinding],
    *,
    today_year: int,
    split: CircuitSplit | None,
    cert: CertStatus | None,
    dispositive: PropFinding | None,
) -> tuple[float, str, str]:
    """→ (risk_score, signal, status)."""
    if dispositive is not None:
        return 1.0, "red", "overruled"

    scored = _scored(findings)
    if not scored:
        # no own treatment, but a watch signal (split/cert) still means "unsettled"
        if (split and split.present) or cert is not None:
            return 0.0, "amber", "watch"
        return 0.0, "unknown", "unknown"

    neg_w = total_w = 0.0
    for f in scored:
        w = court_weight(f.citing_court) * _conf(f) * _recency_factor(f.citing_year, today_year)
        total_w += w
        neg_w += w * _severity(f.treatment)
    score = neg_w / total_w if total_w else 0.0

    eroding = score > _AMBER_FLOOR or (split is not None and split.present) or cert is not None
    if eroding:
        # status names the dominant own-negative when it's a clean "limited"
        negs = [f.treatment for f in scored if _polarity(f.treatment) < 0]
        status = "limited" if negs and set(negs) <= {"limited"} else "good-but-eroding"
        return score, "amber", status
    return score, "green", "good"


# --- close-to-overruled (abstains on conflict) ------------------------------ #
def _close_to_overruled(
    findings: list[PropFinding],
    *,
    split: CircuitSplit | None,
    cert: CertStatus | None,
    dispositive: PropFinding | None,
) -> CloseToOverruled:
    if dispositive is not None:
        return CloseToOverruled(
            flag=True, confidence=0.9,
            rationale="Already overruled/abrogated by a binding high court.",
        )

    scored = _scored(findings)
    high_neg = [f for f in scored if _polarity(f.treatment) < 0 and court_weight(f.citing_court) >= _HIGH_COURT]
    high_pos = [f for f in scored if _polarity(f.treatment) > 0 and court_weight(f.citing_court) >= _HIGH_COURT]
    strong_neg = [f for f in high_neg if f.treatment in STRONG_NEGATIVE]
    split_present = split is not None and split.present
    cert_pending = cert is not None

    # Conflict → abstain. Binding negatives sitting alongside binding reaffirmations
    # is exactly the "don't give a confident wrong answer" case.
    if high_neg and high_pos:
        return CloseToOverruled(
            flag=False, confidence=0.4,
            rationale="Needs review — binding high-court negatives sit alongside binding "
            "reaffirmations; the trajectory is genuinely contested.",
        )

    # Convergent erosion: accelerating strong negatives + an active split.
    if len(strong_neg) >= 2 and split_present:
        return CloseToOverruled(
            flag=True, confidence=0.7,
            rationale="Accelerating high-court strong negatives plus an active circuit split.",
        )

    # A binding negative + split + pending cert is unsettled but not yet over → abstain.
    if high_neg and split_present and cert_pending:
        return CloseToOverruled(
            flag=False, confidence=0.5,
            rationale="Needs review — a binding negative, an active split, and a pending "
            "cert petition; the law may move but has not yet.",
        )

    return CloseToOverruled(
        flag=False, confidence=0.2,
        rationale="No convergent erosion signal; treatment is isolated or approving.",
    )


# --- narrative + timeline + operative rule ---------------------------------- #
def _narrative(findings: list[PropFinding], split: CircuitSplit | None, cert: CertStatus | None) -> str:
    """Grounded by construction: every clause restates a verified finding."""
    scored = _scored(findings)
    parts: list[str] = []
    for f in scored:
        if _polarity(f.treatment) < 0:
            parts.append(
                f"{f.treatment.capitalize()} by {f.citing_case_name} "
                f"({f.citing_court}, {f.citing_year}): {f.what_changed}"
            )
    pos = [f for f in scored if _polarity(f.treatment) > 0]
    if pos:
        who = ", ".join(f"{f.citing_case_name} ({f.citing_court})" for f in pos)
        parts.append(f"Applied/followed by {who}.")
    if split and split.present:
        parts.append(
            f"Circuit split — {', '.join(split.follows)} follow; {', '.join(split.limits)} cut against."
        )
    if cert is not None:
        state = "granted" if cert.granted else "pending, not granted"
        parts.append(f"On the SCOTUS cert watch ({state}, as of {cert.as_of}).")
    return " ".join(parts) if parts else "No substantive treatment in the retrieved set."


def _timeline(findings: list[PropFinding]) -> list[TimelinePoint]:
    pts: list[TimelinePoint] = []
    for f in findings:
        if f.citing_year is None:
            continue
        polarity = 0 if f.attribution == "reported" else _polarity(f.treatment)
        pts.append(
            TimelinePoint(
                year=f.citing_year, court=f.citing_court, case_name=f.citing_case_name,
                treatment=f.treatment, polarity=polarity,
            )
        )
    pts.sort(key=lambda p: p.year)
    return pts


def _supporting_edges(findings: list[PropFinding]) -> list[str]:
    seen: dict[str, None] = {}  # dedupe, preserve order
    for f in findings:
        if f.citing_case_name:
            seen.setdefault(f.citing_case_name, None)
    return list(seen)


def _operative_rule(case_name: str | None, findings: list[PropFinding], today_year: int) -> str:
    name = case_name or "The case"
    scored = _scored(findings)
    disp = _dispositive(scored)
    if disp is not None:
        return f"{name} — no longer good law: {disp.treatment} by {disp.citing_case_name} ({disp.citing_year})."
    # Highest-court, most-recent soft-negative is the "as modified by" gloss.
    mods = [f for f in scored if f.treatment in SOFT_NEGATIVE and court_weight(f.citing_court) >= _HIGH_COURT]
    mods.sort(key=lambda f: (court_weight(f.citing_court), f.citing_year or 0), reverse=True)
    if mods:
        m = mods[0]
        return f"{name} — good law as modified by {m.citing_case_name} ({m.citing_year})."
    return f"{name} — good law."


# --- entry point ------------------------------------------------------------ #
def aggregate_propositions(
    case: CaseRef,
    findings: list[PropFinding],
    *,
    cert_table: dict[str, CertStatus],
    today: date,
) -> PropositionsResponse:
    """Pure: bucket findings by proposition, compute each proposition's verdict, and
    compose the operative rule. ``cert_table`` (curated, code-grounded) is injected —
    this function never asserts a cert grant of its own."""
    today_year = today.year
    by_prop: dict[str, list[PropFinding]] = {}
    for f in findings:
        if f.proposition is None:  # whole-case findings don't attach to a proposition
            continue
        by_prop.setdefault(f.proposition, []).append(f)

    # A proposition gets a verdict if it has findings OR a curated cert-watch entry
    # (so e.g. an AWB/LCM split surfaces even with no direct treatment edge).
    prop_ids = sorted(set(by_prop) | set(cert_table), key=lambda p: _ORDER.get(p, 99))

    verdicts: list[PropositionVerdict] = []
    for pid in prop_ids:
        fs = by_prop.get(pid, [])
        split = _circuit_split(fs)
        cert = cert_table.get(pid)
        disp = _dispositive(fs)
        score, signal, status = _risk(fs, today_year=today_year, split=split, cert=cert, dispositive=disp)
        label, summary = _LABELS.get(pid, (pid, ""))
        verdicts.append(
            PropositionVerdict(
                proposition_id=pid,
                label=label,
                summary=summary,
                signal=signal,
                status=status,
                risk_score=round(score, 3),
                what_changed=_narrative(fs, split, cert),
                timeline=_timeline(fs),
                circuit_split=split,
                cert=cert,
                close_to_overruled=_close_to_overruled(fs, split=split, cert=cert, dispositive=disp),
                supporting_edges=_supporting_edges(fs),
            )
        )

    return PropositionsResponse(
        case=case,
        operative_rule=_operative_rule(case.case_name, findings, today_year),
        propositions=verdicts,
        as_of=today.isoformat(),
    )
