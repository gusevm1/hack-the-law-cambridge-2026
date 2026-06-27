"""Triage tiering unit tests — pure, offline (no LLM, no DB).

Pins the deterministic filter: the real Bruen golden set tiers correctly (Rahimi →
deep, both noise edges → mention, nothing dropped), plus synthetic edges for the
bare-cite and binding/recency boundaries.
"""

from __future__ import annotations

from datetime import date

from htl.citator.golden import BRUEN_CITATIONS, BRUEN_ID
from htl.citator.triage import tier_edges
from htl.models.api import CaseRef, CitingCaseRef, Edge

TODAY = date(2026, 6, 27)
BRUEN = CaseRef(case_id=BRUEN_ID, case_name="New York State Rifle & Pistol Assn., Inc. v. Bruen",
                citation="597 U.S. 1", court="scotus", date_filed="2022-06-23")


def _edge(passage, court="scotus", year=2024, name="Citing Co.") -> Edge:
    return Edge(
        citing_case=CitingCaseRef(case_name=name, court=court, date_filed=f"{year}-01-01"),
        citation="1 F.4th 1", passage=passage, source="graph", matched_citation="597 U.S. 1",
    )


def _by_name(resp, name):
    return next(e for e in resp.edges if e.citing_case.case_name == name)


# --- the real golden set ---------------------------------------------------- #
def test_golden_bruen_tiers() -> None:
    r = tier_edges(BRUEN.model_copy(), BRUEN_CITATIONS.edges, today=TODAY)

    # nothing dropped — every input edge comes back, counts sum to total
    assert r.total == len(BRUEN_CITATIONS.edges)
    assert r.counts.deep + r.counts.shallow + r.counts.mention == r.total

    # apex binding treatment is force-deep
    assert _by_name(r, "United States v. Rahimi").tier == "deep"

    # both noise edges are surfaced as mention, never dropped
    assert _by_name(r, "United States v. Richardson").tier == "mention"  # reversed-direction
    assert _by_name(r, "Lynch v. Jackson").tier == "mention"  # procedural

    # a followed binding-circuit case on multiple propositions earns deep…
    assert _by_name(r, "Antonyuk v. James").tier == "deep"
    # …a single-proposition circuit application is shallow
    assert _by_name(r, "United States v. Jackson").tier == "shallow"


def test_ordering_deep_first() -> None:
    r = tier_edges(BRUEN.model_copy(), BRUEN_CITATIONS.edges, today=TODAY)
    order = {"deep": 0, "shallow": 1, "mention": 2}
    tiers = [order[e.tier] for e in r.edges]
    assert tiers == sorted(tiers)


# --- synthetic boundaries --------------------------------------------------- #
def test_reversed_direction_is_mention() -> None:
    r = tier_edges(BRUEN.model_copy(),
                   [_edge("Smith has been overruled by Bruen.", court="dcd")], today=TODAY)
    assert r.edges[0].tier == "mention"
    assert any("reversed-direction" in x for x in r.edges[0].reasons)


def test_procedural_is_mention() -> None:
    r = tier_edges(BRUEN.model_copy(),
                   [_edge("The motion is overruled by operation of law.")], today=TODAY)
    assert r.edges[0].tier == "mention"


def test_bare_cite_is_mention() -> None:
    # no treatment language, no proposition phrase → bare cite → mention
    r = tier_edges(BRUEN.model_copy(),
                   [_edge("See Bruen, 597 U.S. 1.", court="scotus")], today=TODAY)
    e = r.edges[0]
    assert e.tier == "mention"
    assert e.signals.treatment_kw == [] and e.signals.propositions_engaged == []


def test_apex_strong_treatment_forced_deep() -> None:
    r = tier_edges(BRUEN.model_copy(),
                   [_edge("We hold the means-end test is limited; not a historical twin.")],
                   today=TODAY)
    assert r.edges[0].tier == "deep"


def test_nonbinding_never_deep() -> None:
    # a state court strongly engaging two propositions is still not binding → not deep
    r = tier_edges(BRUEN.model_copy(),
                   [_edge("Applying the means-end test and proper cause analysis.",
                          court="ny")], today=TODAY)
    assert r.edges[0].signals.binding is False
    assert r.edges[0].tier != "deep"


def test_unknown_case_empty_no_crash() -> None:
    r = tier_edges(CaseRef(case_id=999), [], today=TODAY)
    assert r.total == 0
    assert r.counts.deep == r.counts.shallow == r.counts.mention == 0
