"""Ingestion parsing/collection unit tests — offline, network mocked.

The script lives outside the ``htl`` package (app/scripts/), so we load it by
path. No live HTTP, no DB: ``collect_case`` is pure given a fake ``search``.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "scripts" / "ingest_citator.py"
_spec = importlib.util.spec_from_file_location("ingest_citator", _path)
ingest = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = ingest  # @dataclass resolves __module__ via sys.modules
_spec.loader.exec_module(ingest)


def test_strip_highlight_removes_tags_and_unescapes() -> None:
    assert ingest.strip_highlight("a <mark>Roe</mark> &amp; b") == "a Roe & b"
    assert ingest.strip_highlight(None) == ""


def test_pick_citation_prefers_us_reports() -> None:
    assert ingest.pick_citation(["35 L. Ed. 2d 147", "410 U.S. 113"]) == "410 U.S. 113"
    assert ingest.pick_citation([]) is None
    assert ingest.pick_citation("163 U.S. 537") == "163 U.S. 537"


def test_parse_date() -> None:
    assert ingest.parse_date("1973-01-22T00:00:00") == date(1973, 1, 22)
    assert ingest.parse_date(None) is None
    assert ingest.parse_date("not-a-date") is None


def test_short_name_takes_surname_after_v() -> None:
    assert ingest.short_name("New York State Rifle & Pistol Assn., Inc. v. Bruen") == "Bruen"
    assert ingest.short_name("Roe v. Wade") == "Wade"
    assert ingest.short_name(None) is None


def test_passage_window_extracts_around_first_needle() -> None:
    text = ("A" * 5000) + " see 597 U.S. 1 holding " + ("B" * 5000)
    win = ingest.passage_window(text, ["597 U.S. 1"], window=100)
    assert "597 U.S. 1" in win
    assert len(win) <= 220  # ~2*window around the hit, not the whole 10k text
    assert len(win) < len(text)


def test_passage_window_falls_back_to_head_when_needle_absent() -> None:
    text = "Z" * 10000
    win = ingest.passage_window(text, ["Bruen", "597 U.S. 1"], window=100)
    assert len(win) <= 200  # bounded head, never the full opinion
    assert ingest.passage_window(None, ["x"]) is None


def test_case_key_collapses_revision_clusters() -> None:
    # the three real Wooden revision clusters share a key → dedup to one
    a = ingest.case_key("Wooden v. United States", 2022)
    b = ingest.case_key("Wooden v. United States Revisions: 6/25/24", 2022)
    assert a == b
    # different year is a different case
    assert ingest.case_key("Wooden v. United States", 1990) != a


def test_collect_case_searches_graph_by_all_opinion_ids_no_literal_cite() -> None:
    # Recall fix: query the citation graph by *all* sub-opinion ids and DON'T AND a
    # literal reporter string (the "597 U.S. 1" filter is how Rahimi went missing).
    queries: list[str] = []
    target = {"results": [{
        "cluster_id": 6480696, "caseName": "NYSRPA v. Bruen", "court_id": "scotus",
        "citation": ["597 U.S. 1"], "dateFiled": "2022-06-23",
        "opinions": [{"id": 11}, {"id": 22}],  # majority + dissent
    }]}
    citers = {"next": None, "results": [{
        "cluster_id": 999, "caseName": "United States v. Rahimi", "court_id": "scotus",
        "citation": ["602 U.S. 680"], "dateFiled": "2024-06-21",
        "opinions": [{"id": 900, "snippet": "the Bruen framework, clarified"}],
    }]}

    def rec(params: dict) -> dict:
        queries.append(params["q"])
        return citers if params["q"].startswith("cites:") else target

    case = ingest.collect_case(rec, name="NYSRPA v. Bruen", citation="597 U.S. 1",
                               max_edges=60, max_texts=40, pages=1)
    assert case is not None
    citer_q = next(q for q in queries if q.startswith("cites:"))
    assert "cites:(11)" in citer_q and "cites:(22)" in citer_q  # every sub-opinion
    assert '"597 U.S. 1"' not in citer_q  # no literal-citation AND (the Rahimi-killer)
    # Rahimi is captured even though it need not contain the queried reporter string
    assert any(c["case_name"] == "United States v. Rahimi" for c in case.citers)


def test_party_surnames_takes_both_sides_and_drops_generic() -> None:
    # both parties (usage varies: "Roe" vs "Wade"); used as passage-location needles
    assert ingest.party_surnames("Roe v. Wade") == ["roe", "wade"]
    # generic org/government tokens dropped, distinctive surname kept
    assert "bruen" in ingest.party_surnames("New York State Rifle & Pistol Assn., Inc. v. Bruen")
    assert ingest.party_surnames(None) == []


# --- fixtures shaped like real CL v4 search payloads ------------------------ #
_RESOLVE = {
    "results": [
        {  # a wrong-but-similar hit that must be skipped (no exact citation)
            "cluster_id": 999, "caseName": "McTaggart v. Roe v. Wade",
            "court_id": "scotus", "citation": ["541 U.S. 1014"], "dateFiled": "2004-04-26",
            "opinions": [{"id": 999, "snippet": "x"}],
        },
        {
            "cluster_id": 108713, "caseName": "Roe v. Wade", "court_id": "scotus",
            "citation": ["35 L. Ed. 2d 147", "410 U.S. 113"], "dateFiled": "1973-01-22",
            "opinions": [{"id": 108713, "snippet": "Roe text"}],
        },
    ]
}
_CITERS = {
    "next": None,
    "results": [
        {  # state court, oldest — should rank last
            "cluster_id": 300, "caseName": "State v. X", "court_id": "la",
            "citation": ["1 So. 2d 1"], "dateFiled": "1999-01-01",
            "opinions": [{"id": 3000, "snippet": "see Roe, <mark>410 U.S. 113</mark>"}],
        },
        {  # SCOTUS — should rank first
            "cluster_id": 6481357, "caseName": "Dobbs v. Jackson",
            "court_id": "scotus", "citation": ["597 U.S. 215"], "dateFiled": "2022-06-24",
            "opinions": [{"id": 6481357, "snippet": "Roe ... <mark>overruled</mark>"}],
        },
        {  # federal appellate — should rank middle
            "cluster_id": 500, "caseName": "Doe v. Roe", "court_id": "ca9",
            "citation": ["9 F.3d 9"], "dateFiled": "2010-01-01",
            "opinions": [{"id": 5000, "snippet": "cf. Roe, 410 U.S. 113"}],
        },
    ],
}


def _fake_search(params: dict) -> dict:
    return _CITERS if params["q"].startswith("cites:") else _RESOLVE


def test_collect_case_resolves_target_and_builds_graph() -> None:
    case = ingest.collect_case(_fake_search, name="Roe v. Wade", citation="410 U.S. 113",
                               max_edges=60, max_texts=40, pages=1)
    assert case is not None
    assert case.target["id"] == 108713
    assert case.target["court"] == "scotus"
    assert case.target["citation"] == "410 U.S. 113"
    assert case.source == "cl_api"

    # three distinct citers, ranked SCOTUS -> appellate -> state
    assert [c["court"] for c in case.citers] == ["scotus", "ca9", "la"]
    # edges point every citer at the target cluster
    assert set(case.edges) == {(6481357, 108713, 1), (500, 108713, 1), (300, 108713, 1)}
    # the SCOTUS citer's highlighted snippet became plain_text (tags stripped)
    assert case.citers[0]["plain_text"] == "Roe ... overruled"
    # lead opinion ids captured for optional token enrichment
    assert case.opinion_ids[500] == 5000


def test_collect_case_keeps_all_high_courts_and_snippets() -> None:
    # Recall-first: collect keeps every citer's snippet; max_texts now caps *passage
    # enrichment* (the binding set), not the graph.
    case = ingest.collect_case(_fake_search, name="Roe v. Wade", citation="410 U.S. 113",
                               max_edges=60, max_texts=1, pages=1)
    assert case is not None
    assert len(case.edges) == 3  # full graph: scotus + ca9 (high) + la (tail)
    assert all(c["plain_text"] for c in case.citers)  # snippets retained for all


def test_collect_case_caps_tail_but_never_high_courts() -> None:
    # A tight cap drops the lower-court tail (la) but never the binding set (scotus+ca9).
    case = ingest.collect_case(_fake_search, name="Roe v. Wade", citation="410 U.S. 113",
                               max_edges=2, max_texts=1, pages=1)
    assert case is not None
    courts = {c["court"] for c in case.citers}
    assert courts == {"scotus", "ca9"}  # both high courts kept
    assert "la" not in courts  # state-court tail deferred to the crawl
    assert len(case.edges) == 2


def test_collect_case_returns_none_when_unresolved() -> None:
    assert ingest.collect_case(lambda p: {"results": []}, name="X", citation="1 U.S. 1") is None


def test_seed_case_is_real_and_marked() -> None:
    case = ingest.seed_case("410 U.S. 113")
    assert case is not None and case.source == "seed"
    assert case.target["id"] == 108713 and case.target["source"] == "seed"
    dobbs = case.citers[0]
    assert dobbs["case_name"].startswith("Dobbs")
    assert "must be overruled" in dobbs["plain_text"]
    assert case.edges == [(6481357, 108713, 1)]
    assert ingest.seed_case("999 U.S. 999") is None
