"""Proposition aggregation unit tests — pure, offline (no LLM, no DB).

Pins the per-proposition verdict: the real Bruen golden set comes out P1/P2 green,
P2a amber (limited by Rahimi), P5 split (CA8 follows / CA3 limits); plus synthetic
findings for the dispositive-red, cert-surfacing, and abstain-on-conflict boundaries.
"""

from __future__ import annotations

from datetime import date

from htl.citator.certwatch import CERT_WATCH
from htl.citator.evolution import (
    PropFinding,
    aggregate_propositions,
    findings_from_edges,
)
from htl.citator.golden import BRUEN_ID
from htl.citator.golden_analysis import analyze
from htl.models.api import CaseRef, CertStatus

TODAY = date(2026, 6, 27)
BRUEN = CaseRef(case_id=BRUEN_ID, case_name="New York State Rifle & Pistol Assn., Inc. v. Bruen",
                citation="597 U.S. 1", court="scotus", date_filed="2022-06-23")


def _pf(prop, treatment, *, court="scotus", year=2024, name="Citing Co.", attribution="self", conf=0.9):
    return PropFinding(
        proposition=prop, treatment=treatment, what_changed="…", attribution=attribution,
        holding_vs_dicta="holding", quote="…", confidence=conf,
        citing_case_name=name, citing_court=court, citing_year=year,
    )


def _by_id(resp, pid):
    return next(p for p in resp.propositions if p.proposition_id == pid)


# --- the real golden set (backs the FE acceptance) -------------------------- #
def test_golden_bruen_propositions() -> None:
    analyzed = analyze(BRUEN_ID, today=TODAY)
    findings = findings_from_edges(analyzed.edges)
    r = aggregate_propositions(BRUEN.model_copy(), findings, cert_table=CERT_WATCH, today=TODAY)

    # operative rule composes the Rahimi gloss
    assert "good law as modified by United States v. Rahimi" in r.operative_rule

    # P1 / P2 reaffirmed → green; P2a limited by Rahimi → amber
    assert _by_id(r, "P1").signal == "green"
    assert _by_id(r, "P2").signal == "green"
    p2a = _by_id(r, "P2a")
    assert p2a.signal == "amber"
    assert p2a.circuit_split is None  # SCOTUS-only, no circuit divergence

    # P5 is a live circuit split: CA8 follows §922(g), CA3 limits it
    p5 = _by_id(r, "P5")
    assert p5.circuit_split is not None and p5.circuit_split.present
    assert p5.circuit_split.follows == ["ca8"]
    assert p5.circuit_split.limits == ["ca3"]
    assert p5.signal == "amber"  # an active split is not "settled"

    # P4 has no treatment edge but rides the cert watch → surfaced, not hidden
    p4 = _by_id(r, "P4")
    assert p4.cert is not None and p4.cert.granted is False

    # every verdict carries a grounded narrative + supporting edges
    assert all(v.what_changed for v in r.propositions)


# --- acceptance boundaries (synthetic findings) ----------------------------- #
def test_circuit_split_detected() -> None:
    findings = [
        _pf("P5", "followed", court="ca8", name="United States v. Jackson"),
        _pf("P5", "limited", court="ca3", name="Range v. Attorney General"),
    ]
    r = aggregate_propositions(BRUEN.model_copy(), findings, cert_table={}, today=TODAY)
    split = _by_id(r, "P5").circuit_split
    assert split is not None and split.present
    assert split.follows == ["ca8"] and split.limits == ["ca3"]


def test_dispositive_high_court_negative_is_red() -> None:
    findings = [_pf("P1", "overruled", court="scotus", name="Some SCOTUS case", conf=0.9)]
    r = aggregate_propositions(BRUEN.model_copy(), findings, cert_table={}, today=TODAY)
    p1 = _by_id(r, "P1")
    assert p1.signal == "red"
    assert p1.status == "overruled"
    assert p1.risk_score == 1.0


def test_cert_flag_surfaces() -> None:
    cert = {"P4": CertStatus(granted=True, case_name="Snope (AWB)", term="OT2025",
                             source="supremecourt.gov", as_of="2026-06-27")}
    r = aggregate_propositions(BRUEN.model_copy(), [], cert_table=cert, today=TODAY)
    p4 = _by_id(r, "P4")
    assert p4.cert is not None and p4.cert.granted is True
    assert p4.signal == "amber"  # on the watch list → unsettled, surfaced


def test_close_to_overruled_abstains_on_conflict() -> None:
    # a binding negative AND a binding reaffirmation on the same proposition → abstain
    findings = [
        _pf("P5", "limited", court="ca3", name="Range"),
        _pf("P5", "followed", court="ca8", name="Jackson"),
    ]
    r = aggregate_propositions(BRUEN.model_copy(), findings, cert_table={}, today=TODAY)
    c2o = _by_id(r, "P5").close_to_overruled
    assert c2o.flag is False
    assert "review" in c2o.rationale.lower()


def test_reported_echo_does_not_score() -> None:
    # a citer merely echoing Rahimi's "trapped in amber" (reported) must not be scored
    # as its own overruling — the attribution trap.
    findings = [_pf("P2a", "overruled", court="scotus", name="Echo Co.", attribution="reported", conf=0.95)]
    r = aggregate_propositions(BRUEN.model_copy(), findings, cert_table={}, today=TODAY)
    p2a = _by_id(r, "P2a")
    assert p2a.signal != "red"  # reported echo is not dispositive
    assert p2a.timeline[0].polarity == 0  # echo carries no own polarity
