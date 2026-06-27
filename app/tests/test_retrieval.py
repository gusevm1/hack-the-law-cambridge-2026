"""Retrieval loader — the wire boundary that turns DB rows into the citations
contract. Pins the row→Edge mapping and the golden fallback. DB session is faked
(the live join is exercised against real Postgres, per the repo pattern).
"""

from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace

from htl.citator.golden import BRUEN_ID
from htl.citator.retrieval import _opinion_url, load_citations


def test_opinion_url_slugifies() -> None:
    assert (
        _opinion_url(6480696, "United States v. Rahimi")
        == "https://www.courtlistener.com/opinion/6480696/united-states-v-rahimi/"
    )
    assert _opinion_url(1, None) == "https://www.courtlistener.com/opinion/1/case/"


class _Result:
    def __init__(self, first: object = None, rows: list | None = None) -> None:
        self._first, self._rows = first, rows or []

    def scalars(self) -> "_Result":
        return self

    def first(self) -> object:
        return self._first

    def all(self) -> list:
        return self._rows


class _SeqSession:
    """Returns queued results in call order: first execute() = the target row,
    second = the edge rows (the two queries load_citations issues)."""

    def __init__(self, *results: _Result) -> None:
        self._results, self._i = list(results), 0

    async def execute(self, *_a: object, **_k: object) -> _Result:
        out = self._results[self._i]
        self._i += 1
        return out

    async def scalar(self, *_a: object, **_k: object) -> int:
        return 0


def test_empty_db_falls_back_to_golden() -> None:
    sess = _SeqSession(_Result(first=None), _Result(rows=[]))
    resp = asyncio.run(load_citations(sess, BRUEN_ID))
    assert resp.case.case_id == BRUEN_ID
    assert resp.total == len(resp.edges) and resp.total > 0  # the golden Bruen edges


def test_db_rows_map_to_edges() -> None:
    case_row = SimpleNamespace(
        case_name="NYSRPA v. Bruen", citation="597 U.S. 1", court="scotus",
        date_filed=date(2022, 6, 23),
    )
    edge_row = SimpleNamespace(
        id=999, case_name="United States v. Rahimi", court="scotus",
        date_filed=date(2024, 6, 21), citation="602 U.S. 680",
        plain_text="...not a law trapped in amber...", source="cl_api",
    )
    sess = _SeqSession(_Result(first=case_row), _Result(rows=[edge_row]))
    resp = asyncio.run(load_citations(sess, BRUEN_ID))

    assert resp.case.date_filed == "2022-06-23"
    assert resp.total == 1
    e = resp.edges[0]
    assert e.citing_case.case_name == "United States v. Rahimi"
    assert e.citing_case.court == "scotus"
    assert e.citing_case.date_filed == "2024-06-21"
    assert e.passage == "...not a law trapped in amber..."
    assert e.source == "cl_api"
    assert e.opinion_url.endswith("/opinion/999/united-states-v-rahimi/")
