"""Mock of Contract A (``/cases/{id}/analyze``) — the deep analyzer's output.

Feature 4 (B) consumes per-edge ``PropositionFinding``s. Feature 3 (A) builds the
real ``/analyze`` in parallel; until it lands, this stub stands in **to the
contract**, exactly as Feature 1 mocked the citations engine.

It reuses the real Bruen golden citations + the deterministic triage, then attaches
the lawyer-confirmed findings per citer (keyed by citing case name). Quotes are
verbatim spans of each edge's passage (what the real analyzer would verify). One
case can touch several propositions, so findings is a list; ``mention`` edges (the
two noise edges) get no findings.

ponytail: swap ``analyze`` for a call into Feature 3's ``/analyze`` route function
once it exists — same ``AnalyzeResponse`` shape, so nothing downstream changes.
"""

from __future__ import annotations

from datetime import date

from htl.citator.golden import CITATIONS
from htl.citator.triage import tier_edges
from htl.models.api import AnalyzedEdge, AnalyzeResponse, PropositionFinding

_DEEP = {"deep", "shallow"}


def _f(prop: str | None, treatment: str, what_changed: str, quote: str, conf: float) -> PropositionFinding:
    return PropositionFinding(
        proposition=prop, treatment=treatment, what_changed=what_changed,
        holding_vs_dicta="holding", attribution="self", quote=quote, confidence=conf,
    )


# Lawyer-confirmed findings per citer (scope §4/§5). Keyed by citing case name.
_FINDINGS: dict[str, list[PropositionFinding]] = {
    "United States v. Rahimi": [
        _f("P2", "followed",
           "Reaffirms the text-history-tradition methodology of Bruen.",
           "Some courts have misunderstood the methodology of our recent Second Amendment cases.",
           0.85),
        _f("P2a", "limited",
           "Clarifies/narrows the analogue test — not a 'dead ringer' or 'historical twin'; "
           "the rigid reading is rejected. The binding gloss on Bruen.",
           'A historical regulation need not be a "dead ringer" or a "historical twin"; '
           "it need only be relevantly similar.",
           0.9),
    ],
    "Antonyuk v. James": [
        _f("P1", "followed",
           "Applies Bruen to strike New York's may-issue 'proper cause' regime.",
           'Applying Bruen, we hold New York\'s may-issue "proper cause" standard is unconstitutional',
           0.85),
        _f("P3", "followed",
           "Upholds most of New York's sensitive-place restrictions as historically grounded.",
           "most of the State's sensitive-place restrictions survive as consistent with the historical tradition",
           0.7),
    ],
    "United States v. Jackson": [
        _f("P5", "followed",
           "Upholds §922(g)(1)'s categorical felon bar under the Bruen/Rahimi framework.",
           "922(g)(1)'s categorical bar on the possession of firearms by those who are "
           "not law-abiding is consistent with the Nation's historical tradition",
           0.8),
    ],
    "Range v. Attorney General": [
        _f("P5", "limited",
           "Cuts against categorical disarmament — a non-dangerous person remains among "
           "'the people'; §922(g) fails as-applied.",
           "the Government has not shown a historical tradition supporting the as-applied "
           "disarmament of Range",
           0.78),
    ],
    "Wolford v. Lopez": [
        _f("P3", "limited",
           "Largely upholds sensitive-place designations but strikes the private-property "
           "default for lack of a historical analogue.",
           "the default rule barring carry on private property open to the public lacks a "
           "historical analogue",
           0.72),
    ],
}

_SUMMARY: dict[str, str] = {
    "United States v. Rahimi": "Clarifies the analogue methodology; does not overrule Bruen.",
    "Antonyuk v. James": "Applies Bruen across public-carry and sensitive places.",
    "United States v. Jackson": "Upholds §922(g)(1) post-Bruen/Rahimi.",
    "Range v. Attorney General": "Strikes §922(g) as-applied to a non-dangerous person.",
    "Wolford v. Lopez": "Mixed result on Hawaii's sensitive places.",
}


def analyze(case_id: int, *, today: date) -> AnalyzeResponse | None:
    """Build the mock ``AnalyzeResponse`` for a target, or None if not in the golden set."""
    hit = CITATIONS.get(case_id)
    if hit is None:
        return None
    triaged = tier_edges(hit.case, hit.edges, today=today)
    edges: list[AnalyzedEdge] = []
    analyzed = 0
    for te in triaged.edges:
        name = te.citing_case.case_name or ""
        findings = _FINDINGS.get(name, []) if te.tier in _DEEP else []
        if te.tier in _DEEP:
            analyzed += 1
        edges.append(
            AnalyzedEdge(
                **te.model_dump(),
                analysis_depth="full-text" if te.tier == "deep" else "snippet",
                findings=findings,
                case_summary=_SUMMARY.get(name, ""),
                model="mock-golden",
            )
        )
    return AnalyzeResponse(
        case=hit.case, total=triaged.total, counts=triaged.counts, analyzed=analyzed, edges=edges
    )
