"""Use-aware verdict tests — offline (no Vertex).

Covers the pure intersection logic (``compose_verdict``), the use→proposition mapper
(deterministic dropdown path, LLM path mocked, fallback), and the route wiring.
"""

from __future__ import annotations

import asyncio
from datetime import date

from fastapi.testclient import TestClient

import htl.llm.usemap as usemap_mod
import htl.llm.vertex as vertex
from htl.citator.propositions_mock import propositions_for
from htl.citator.verdict import compose_verdict
from htl.llm.usemap import USE_DEFAULTS, map_use_to_propositions
from htl.main import app
from htl.models.api import UseMapping

BRUEN = 6480696


def _props():
    return propositions_for(BRUEN, today=date(2026, 6, 27))


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
    assert "relevantly similar" in v.risk_explanation  # pulls Contract B's what_changed
    p2a = next(p for p in v.per_proposition if p.proposition_id == "P2a")
    assert p2a.relevant_to_use and p2a.signal == "amber"


def test_unmapped_use_degrades_to_review() -> None:
    v = compose_verdict(_props(), _mapping([]))
    assert v.real_risk is False
    assert "review" in v.risk_explanation.lower()
    assert v.close_to_overruled.flag is False


def test_engaged_but_unanalysed_proposition_is_not_a_false_allclear() -> None:
    # P4 isn't in the Bruen mock — must not read as a confident "safe".
    v = compose_verdict(_props(), _mapping(["P4"]))
    assert v.real_risk is False
    assert "review manually" in v.risk_explanation


def test_operative_rule_and_splits_in_final_labels() -> None:
    v = compose_verdict(_props(), _mapping(["P5"]))
    assert any(lbl.startswith("Good law as modified") for lbl in v.final_labels)
    assert "circuit split on P5" in v.final_labels


# --- use → proposition mapping ---------------------------------------------- #
def test_dropdown_use_maps_deterministically_without_vertex(monkeypatch) -> None:
    # A known dropdown use with no free-form intent must NOT call the model.
    def _boom() -> None:
        raise AssertionError("Vertex must not be called on the deterministic path")

    monkeypatch.setattr(vertex, "_get_client", _boom)
    m = asyncio.run(map_use_to_propositions("History-and-tradition test (P2/P2a)", ""))
    assert m.engaged_propositions == ["P2", "P2a"]
    assert all(u in USE_DEFAULTS for u in [m.use_label])


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


# --- route ------------------------------------------------------------------ #
def test_route_returns_use_aware_verdict() -> None:
    # Dropdown use + empty intent → deterministic, no Vertex; full pipeline via route.
    r = TestClient(app).post(
        "/cases/6480696/verdict", json={"use": "Public-carry right (P1)", "intent": ""}
    )
    assert r.status_code == 200
    j = r.json()
    assert j["real_risk"] is False
    assert j["use"]["engaged_propositions"] == ["P1"]
    assert [p["proposition_id"] for p in j["per_proposition"]] == ["P1", "P2", "P2a", "P3", "P5"]
    assert any(lbl.startswith("Good law as modified") for lbl in j["final_labels"])
