"""Edge classifier tests — offline (no Vertex). Exercises the keyword fallback,
the Vertex-unavailable path, and the /cases/{id}/classify route wiring (mentions
stay unclassified; deep+shallow get a classification; counts/order preserved).
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

import htl.llm.vertex as vertex
import htl.routes.classify as classify_route
from htl.citator.propositions import PROP_IDS, SPINE_TEXT
from htl.llm.classify import EdgeClass, classify_edge, classify_edge_keyword
from htl.main import app


def test_spine_integrity() -> None:
    assert "P2a" in PROP_IDS and PROP_IDS[0] == "P1"
    assert "P2a" in SPINE_TEXT  # the model prompt actually lists the spine


def test_keyword_fallback_takes_proposition_from_filter() -> None:
    c = classify_edge_keyword("The court distinguished Bruen on its facts.", ["P5", "P1"])
    assert c.treatment == "distinguished"
    assert c.proposition == "P5"  # first candidate from the deterministic filter
    assert c.model == "keyword-fallback"


def test_classify_edge_falls_back_when_vertex_down(monkeypatch) -> None:
    def _boom() -> None:
        raise RuntimeError("vertex predict blocked for this identity")

    monkeypatch.setattr(vertex, "_get_client", _boom)
    res = asyncio.run(classify_edge("Bruen is overruled in part.", "Bruen", "597 U.S. 1", ["P2a"]))
    assert res.model == "keyword-fallback"
    assert res.treatment == "overruled"
    assert res.proposition == "P2a"


def test_empty_passage_is_neutral() -> None:
    res = asyncio.run(classify_edge("   ", "Bruen", None, None))
    assert res.treatment == "cited-neutral"
    assert res.proposition is None


def _fake_classify(passage, target_name=None, target_citation=None, candidate_propositions=None):
    async def _run() -> EdgeClass:
        prop = candidate_propositions[0] if candidate_propositions else None
        return EdgeClass("followed", prop, "holding", "self", (passage or "")[:20], 0.9, "test-stub")

    return _run()


def test_classify_route_only_classifies_deep_and_shallow(monkeypatch) -> None:
    monkeypatch.setattr(classify_route, "classify_edge", _fake_classify)
    r = TestClient(app).get("/cases/6480696/classify")
    assert r.status_code == 200
    j = r.json()

    assert j["total"] == len(j["edges"])
    assert j["classified"] == j["counts"]["deep"] + j["counts"]["shallow"]

    for e in j["edges"]:
        if e["tier"] == "mention":
            assert e["classification"] is None  # noise surfaced, not classified
        else:
            assert e["classification"]["model"] == "test-stub"

    # deep-first ordering carried over from triage
    order = {"deep": 0, "shallow": 1, "mention": 2}
    tiers = [order[e["tier"]] for e in j["edges"]]
    assert tiers == sorted(tiers)
