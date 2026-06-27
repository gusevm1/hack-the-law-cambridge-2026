"""Use-aware verdict tests — offline (no Vertex, no DB).

Pure intersection logic (``compose_verdict``) is tested on a small hand-built
Contract-B fixture so it's isolated from Feature 4's data. The mapper's three paths
(deterministic dropdown / LLM / fallback) and the route — which integrates Feature
4's real ``/propositions`` end-to-end — are exercised separately.
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

import htl.llm.usemap as usemap_mod
import htl.llm.vertex as vertex
from htl.citator.verdict import compose_verdict
from htl.llm.usemap import USE_DEFAULTS, map_use_to_propositions
from htl.main import app
from htl.models.api import (
    CaseRef,
    CircuitSplit,
    CloseToOverruled,
    PropositionsResponse,
    PropositionVerdict,
    UseMapping,
)

BRUEN = 6480696
_NOT_CLOSE = CloseToOverruled(flag=False, confidence=0.9, rationale="Not close to overruled.")


def _props() -> PropositionsResponse:
    """A minimal Contract-B response: P1 green, P2a amber, P5 amber (with a split)."""
    props = [
        PropositionVerdict(
            proposition_id="P1", label="Public-carry right", summary="", signal="green",
            status="good", risk_score=0.1, what_changed="Reaffirmed; no binding negative.",
            close_to_overruled=_NOT_CLOSE,
        ),
        PropositionVerdict(
            proposition_id="P2a", label="Analogue not twin", summary="", signal="amber",
            status="limited", risk_score=0.55,
            what_changed="Rahimi rejected the rigid 'dead ringer / historical twin' reading.",
            close_to_overruled=_NOT_CLOSE,
        ),
        PropositionVerdict(
            proposition_id="P5", label="The people / §922(g)", summary="", signal="amber",
            status="good-but-eroding", risk_score=0.6, what_changed="Categorical vs as-applied split.",
            circuit_split=CircuitSplit(present=True, follows=["ca8"], limits=["ca3"], summary="split"),
            close_to_overruled=_NOT_CLOSE,
        ),
    ]
    return PropositionsResponse(
        case=CaseRef(case_id=BRUEN, case_name="Bruen"),
        operative_rule="Good law as modified by United States v. Rahimi (2024).",
        propositions=props, as_of="2026-06-27",
    )


def _mapping(ids, use="some use", intent=""):
    return UseMapping(use_label=use, intent=intent, engaged_propositions=ids, rationale="t")


# --- pure compose_verdict --------------------------------------------------- #
def test_use_p1_only_is_safe_despite_p2a_erosion() -> None:
    v = compose_verdict(_props(), _mapping(["P1"]))
    assert v.real_risk is False
    p1 = next(p for p in v.per_proposition if p.proposition_id == "P1")
    assert p1.relevant_to_use and p1.signal == "green"
    p2a = next(p for p in v.per_proposition if p.proposition_id == "P2a")
    assert not p2a.relevant_to_use and p2a.signal == "amber"  # eroded, but not engaged
    assert "Safe for this use" in v.risk_explanation
    assert "close to overruled: no" in v.final_labels


def test_use_p2a_is_real_risk_with_explanation() -> None:
    v = compose_verdict(_props(), _mapping(["P2a"]))
    assert v.real_risk is True
    assert "Real risk for this use" in v.risk_explanation
    assert "historical twin" in v.risk_explanation  # pulls Contract B's what_changed
    p2a = next(p for p in v.per_proposition if p.proposition_id == "P2a")
    assert p2a.relevant_to_use and p2a.signal == "amber"


def test_unmapped_use_degrades_to_review() -> None:
    v = compose_verdict(_props(), _mapping([]))
    assert v.real_risk is False
    assert "review" in v.risk_explanation.lower()
    assert v.close_to_overruled.flag is False


def test_engaged_but_unanalysed_proposition_is_not_a_false_allclear() -> None:
    # P4 isn't in this fixture — must not read as a confident "safe".
    v = compose_verdict(_props(), _mapping(["P4"]))
    assert v.real_risk is False
    assert "review manually" in v.risk_explanation


def test_operative_rule_and_splits_in_final_labels() -> None:
    v = compose_verdict(_props(), _mapping(["P5"]))
    assert v.final_labels[0] == "Good law as modified by United States v. Rahimi (2024)."
    assert "circuit split on P5" in v.final_labels


# --- use → proposition mapping ---------------------------------------------- #
def test_dropdown_use_maps_deterministically_without_vertex(monkeypatch) -> None:
    # A known dropdown use with no free-form intent must NOT call the model.
    def _boom() -> None:
        raise AssertionError("Vertex must not be called on the deterministic path")

    monkeypatch.setattr(vertex, "_get_client", _boom)
    m = asyncio.run(map_use_to_propositions("History-and-tradition test (P2/P2a)", ""))
    assert m.engaged_propositions == ["P2", "P2a"]
    assert m.use_label in USE_DEFAULTS


def test_offmenu_intent_maps_via_llm(monkeypatch) -> None:
    async def _fake_vertex(use, intent, defaults):
        return ["P5"], "the use turns on who may be disarmed"

    monkeypatch.setattr(usemap_mod, "_map_vertex", _fake_vertex)
    m = asyncio.run(map_use_to_propositions("off-menu use", "disarming a felon client"))
    assert m.engaged_propositions == ["P5"]
    assert "disarmed" in m.rationale


def test_llm_failure_falls_back_to_dropdown_default(monkeypatch) -> None:
    async def _boom(use, intent, defaults):
        raise RuntimeError("vertex down")

    monkeypatch.setattr(usemap_mod, "_map_vertex", _boom)
    m = asyncio.run(map_use_to_propositions("Felon / §922(g) disqualification (P5)", "as-applied"))
    assert m.engaged_propositions == ["P5"]  # default kicks in despite the intent


# --- route (integrates Feature 4's real /propositions, offline golden) ------ #
def test_route_p1_use_is_safe() -> None:
    r = TestClient(app).post(
        "/cases/6480696/verdict", json={"use": "Public-carry right (P1)", "intent": ""}
    )
    assert r.status_code == 200
    j = r.json()
    assert j["use"]["engaged_propositions"] == ["P1"]
    assert j["real_risk"] is False
    assert j["final_labels"][0] == j["operative_rule"]
    assert any(p["proposition_id"] == "P1" for p in j["per_proposition"])


def test_route_p4_use_is_real_risk() -> None:
    # P4 (assault-weapon / magazine ban) is amber in Feature 4's Bruen analysis.
    r = TestClient(app).post(
        "/cases/6480696/verdict",
        json={"use": "Assault-weapon / magazine ban (P4)", "intent": ""},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["use"]["engaged_propositions"] == ["P4"]
    assert j["real_risk"] is True
    p4 = next(p for p in j["per_proposition"] if p["proposition_id"] == "P4")
    assert p4["relevant_to_use"] is True
