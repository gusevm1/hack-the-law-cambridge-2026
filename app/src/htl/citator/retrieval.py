"""Load real retrieved citations from the DB — the wire boundary the analysis
pipeline reads (``GET /cases/{id}/citations`` and the triage → classify → analyze
stages all go through here).

Mirrors ``routes/risk.py``'s join: the target row from ``cl_opinions``, its inbound
edges from ``citation_edges ⋈ cl_opinions`` on ``citing_id``. Each row maps to the
wire ``Edge`` — ``passage`` is the citer's stored span (``plain_text``), ``opinion_url``
is derived from the citing cluster id. See ``.claude/handoffs/retrieval-ingestion-
contract.md`` §1–2 for the contract this fulfils.

Falls back to the Bruen golden stub when the DB has nothing for the id, so the demo
and the offline tests (no Postgres) keep working with no ingest run.

ponytail: ``source`` carries the row's provenance (``cl_api`` / ``seed``) as the badge;
``matched_citation`` isn't persisted per-edge yet (null). Add both as edge columns if
the provenance badge needs the graph-vs-fulltext split the contract sketches.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from htl.citator.golden import CITATIONS
from htl.citator.risk import polarity_label
from htl.db.citator import CitationEdge, ClOpinion, Treatment
from htl.models.api import CaseRef, CitationsResponse, CitingCaseRef, Edge

_SLUG = re.compile(r"[^a-z0-9]+")
_SEVERITY = {"negative": 2, "positive": 1, "neutral": 0}


def _opinion_url(citing_id: int, name: str | None) -> str:
    """CourtListener matches on the numeric id and normalises the slug, so any
    reasonable slug resolves to the canonical opinion URL (the receipt)."""
    slug = _SLUG.sub("-", (name or "case").lower()).strip("-") or "case"
    return f"https://www.courtlistener.com/opinion/{citing_id}/{slug}/"


async def _worst_treatment_by_citer(session: AsyncSession, case_id: int) -> dict[int, str]:
    """Most-severe persisted treatment type per citing case (negative > positive >
    neutral). Matches /graph's pick-the-worst so the analyze gate and the graph
    colour agree on whether a citer treats the target neutrally."""
    rows = (
        await session.execute(
            select(Treatment.citing_id, Treatment.type).where(Treatment.cited_id == case_id)
        )
    ).all()
    worst: dict[int, str] = {}
    for citing_id, type_ in rows:
        if type_ is None:
            continue
        cur = worst.get(citing_id)
        if cur is None or _SEVERITY[polarity_label(type_)] > _SEVERITY[polarity_label(cur)]:
            worst[citing_id] = type_
    return worst


async def load_citations(session: AsyncSession, case_id: int) -> CitationsResponse:
    case_row = (
        await session.execute(select(ClOpinion).where(ClOpinion.id == case_id))
    ).scalars().first()

    rows = (
        await session.execute(
            select(
                ClOpinion.id,
                ClOpinion.case_name,
                ClOpinion.court,
                ClOpinion.date_filed,
                ClOpinion.citation,
                ClOpinion.plain_text,
                ClOpinion.source,
            )
            .join(CitationEdge, CitationEdge.citing_id == ClOpinion.id)
            .where(CitationEdge.cited_id == case_id)
        )
    ).all()

    # Nothing ingested for this id → the contract-true golden stub (demo + offline tests).
    if case_row is None and not rows:
        return CITATIONS.get(case_id) or CitationsResponse(
            case=CaseRef(case_id=case_id), total=0, edges=[]
        )

    case = CaseRef(
        case_id=case_id,
        case_name=case_row.case_name if case_row else None,
        citation=case_row.citation if case_row else None,
        court=case_row.court if case_row else None,
        date_filed=case_row.date_filed.isoformat() if case_row and case_row.date_filed else None,
    )
    worst = await _worst_treatment_by_citer(session, case_id)
    edges = [
        Edge(
            citing_case=CitingCaseRef(
                case_name=r.case_name,
                court=r.court,
                date_filed=r.date_filed.isoformat() if r.date_filed else None,
            ),
            citation=r.citation,
            passage=r.plain_text or "",
            source=r.source or "graph",
            matched_citation=None,
            opinion_url=_opinion_url(r.id, r.case_name),
            treatment=worst.get(r.id),
        )
        for r in rows
    ]
    return CitationsResponse(case=case, total=len(edges), edges=edges)
