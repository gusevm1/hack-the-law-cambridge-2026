"""Deep analyzer tests — offline (no Vertex). Exercises both modes (full-text vs
snippet), the graceful degradation when Vertex is down, and the /cases/{id}/analyze
route wiring (mentions not analyzed; analyzed == deep+shallow; full-text edge yields
multiple findings; deep-first order preserved).
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

import htl.llm.analyze as analyze
import htl.llm.vertex as vertex
import htl.routes.analyze as analyze_route
from htl.citator.golden import BRUEN_ID, full_text_for
from htl.llm.analyze import EdgeAnalysis, Finding, analyze_edge
from htl.main import app
from htl.models.api import CaseRef, CitingCaseRef, TieredEdge, TriageSignals

_CASE = CaseRef(case_id=BRUEN_ID, case_name="Bruen", citation="597 U.S. 1", court="scotus")


def _edge(passage: str, *, court: str = "ca3", props: list[str] | None = None) -> TieredEdge:
    return TieredEdge(
        citing_case=CitingCaseRef(case_name="Some v. Case", court=court, date_filed="2024-01-01"),
        citation="1 F.4th 1",
        passage=passage,
        source="graph",
        matched_citation="597 U.S. 1",
        tier="shallow",
        reasons=[],
        signals=TriageSignals(binding=True, treatment_kw=[], propositions_engaged=props or [],
                              recency_years=2),
    )


def test_snippet_mode_one_finding_lowered_confidence(monkeypatch) -> None:
    # Vertex down → classify_edge keyword fallback → one finding, snippet depth.
    monkeypatch.setattr(vertex, "_get_client", lambda: (_ for _ in ()).throw(RuntimeError("blocked")))
    res = asyncio.run(analyze_edge(_edge("The court distinguished Bruen on its facts.", props=["P5"]),
                                   _CASE, None))
    assert res.analysis_depth == "snippet"
    assert len(res.findings) == 1
    f = res.findings[0]
    assert f.treatment == "distinguished"
    assert f.proposition == "P5"  # taken from the filter's phrase hits
    assert f.confidence < 0.4  # 0.4 keyword conf, discounted for snippet depth
    assert res.model == "keyword-fallback"


def test_fulltext_mode_multiple_findings(monkeypatch) -> None:
    async def _fake(full_text, name, citation):
        return EdgeAnalysis(
            "full-text",
            [Finding("P2a", "limited", "narrows the rigid reading", "holding", "self", "", 0.9),
             Finding("P5", "limited", "rejects 'responsible'", "holding", "self", "", 0.8)],
            "good law as modified", "gemini-test",
        )

    monkeypatch.setattr(analyze, "_analyze_fulltext_vertex", _fake)
    res = asyncio.run(analyze_edge(_edge("snippet ignored"), _CASE, "FULL OPINION TEXT"))
    assert res.analysis_depth == "full-text"
    assert {f.proposition for f in res.findings} == {"P2a", "P5"}


def test_fulltext_degrades_to_snippet_when_vertex_down(monkeypatch) -> None:
    monkeypatch.setattr(vertex, "_get_client", lambda: (_ for _ in ()).throw(RuntimeError("blocked")))
    res = asyncio.run(analyze_edge(_edge("Bruen is overruled in part.", props=["P2a"]),
                                   _CASE, "FULL TEXT PRESENT"))
    assert res.analysis_depth == "snippet"  # honest: we never got the deep read
    assert res.findings[0].treatment == "overruled"


def test_rahimi_edge_carries_full_text() -> None:
    assert full_text_for("United States v. Rahimi")  # full-text mode is exercised
    assert full_text_for("Wolford v. Lopez") is None  # snippet-only


def _fake_analyze(edge, case, full_text):
    async def _run() -> EdgeAnalysis:
        if full_text:
            return EdgeAnalysis("full-text",
                                [Finding("P2a", "limited", "x", "holding", "self", "", 0.9),
                                 Finding("P5", "limited", "y", "holding", "self", "", 0.8)],
                                "summary", "test-stub")
        return EdgeAnalysis("snippet", [Finding(None, "followed", "z", "holding", "self", "", 0.7)],
                            "summary", "test-stub")

    return _run()


def test_analyze_route(monkeypatch) -> None:
    monkeypatch.setattr(analyze_route, "analyze_edge", _fake_analyze)
    r = TestClient(app).get(f"/cases/{BRUEN_ID}/analyze")
    assert r.status_code == 200
    j = r.json()

    assert j["total"] == len(j["edges"])
    assert j["analyzed"] == j["counts"]["deep"] + j["counts"]["shallow"]

    depths = set()
    for e in j["edges"]:
        if e["tier"] == "mention":
            assert e["findings"] == []  # surfaced, not analyzed
            assert e["model"] == ""
        else:
            assert e["model"] == "test-stub"
            assert len(e["findings"]) >= 1
            depths.add(e["analysis_depth"])

    assert "full-text" in depths  # Rahimi carries full text → full-text mode

    # deep-first ordering carried over from triage
    order = {"deep": 0, "shallow": 1, "mention": 2}
    tiers = [order[e["tier"]] for e in j["edges"]]
    assert tiers == sorted(tiers)
