"""GET /cases/{id}/graph — the inbound treatment network for the graph view.

PUBLIC, like /resolve and /risk. Pairs with /risk: /risk is the verdict, /graph is
the evidence you can click. ``id`` is a CourtListener cluster id (==
``cl_opinions.id`` == ``citation_edges.cited_id``).

For each citer we emit one node + one edge; the edge carries the *most severe*
treatment (so the colour matches the verdict) and a deep link to the citing
opinion — the receipt. The focal ``signal`` is computed by the same
``aggregate_risk`` the verdict uses, so the two surfaces can never disagree.
"""

from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter
from sqlalchemy import func, select

from htl.citator.risk import NEGATIVE, POSITIVE, CitingTreatment, aggregate_risk
from htl.db.citator import CitationEdge, ClOpinion, Treatment
from htl.models.api import CaseRef, GraphEdge, GraphNode, GraphResponse
from htl.routes.dependencies import DbSession

router = APIRouter()

_CL_OPINION = "https://www.courtlistener.com/opinion/{cid}/{slug}/"
_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(name: str | None) -> str:
    """A best-effort slug; CourtListener matches on the numeric id and normalises
    the slug, so any reasonable value resolves to the canonical opinion URL."""
    s = _SLUG.sub("-", (name or "case").lower()).strip("-")
    return s or "case"


def _source_url(cluster_id: int, name: str | None) -> str:
    return _CL_OPINION.format(cid=cluster_id, slug=_slug(name))


def _polarity(type_: str | None) -> str:
    if type_ in NEGATIVE:
        return "negative"
    if type_ in POSITIVE:
        return "positive"
    return "neutral"


def _rank(type_: str | None, conf: float | None) -> tuple[int, float]:
    """Pick-the-worst ordering per citer: negative > positive > neutral, then conf."""
    pol = {"negative": 2, "positive": 1, "neutral": 0}[_polarity(type_)]
    return (pol, conf if conf is not None else 0.0)


@router.get("/cases/{case_id}/graph", response_model=GraphResponse)
async def case_graph(case_id: int, session: DbSession) -> GraphResponse:
    focal_row = (
        await session.execute(select(ClOpinion).where(ClOpinion.id == case_id))
    ).scalars().first()
    focal = CaseRef(
        case_id=case_id,
        case_name=focal_row.case_name if focal_row else None,
        citation=focal_row.citation if focal_row else None,
        court=focal_row.court if focal_row else None,
        date_filed=(
            focal_row.date_filed.isoformat() if focal_row and focal_row.date_filed else None
        ),
    )

    # Citers + their metadata (one row per inbound edge).
    citer_rows = (
        await session.execute(
            select(
                ClOpinion.id,
                ClOpinion.case_name,
                ClOpinion.citation,
                ClOpinion.court,
                ClOpinion.date_filed,
            )
            .join(CitationEdge, CitationEdge.citing_id == ClOpinion.id)
            .where(CitationEdge.cited_id == case_id)
        )
    ).all()

    # Treatments keyed by citer; keep the most severe per citer for the edge.
    treat_rows = (
        await session.execute(
            select(
                Treatment.citing_id,
                Treatment.type,
                Treatment.scope,
                Treatment.on_other_grounds,
                Treatment.quote,
                Treatment.confidence,
            ).where(Treatment.cited_id == case_id)
        )
    ).all()
    worst: dict[int, tuple] = {}
    for r in treat_rows:
        if r.type is None:
            continue
        cur = worst.get(r.citing_id)
        if cur is None or _rank(r.type, r.confidence) > _rank(cur.type, cur.confidence):
            worst[r.citing_id] = r

    nodes: list[GraphNode] = [
        GraphNode(
            case_id=case_id,
            case_name=focal.case_name,
            citation=focal.citation,
            court=focal.court,
            date_filed=focal.date_filed,
            is_focal=True,
        )
    ]
    edges: list[GraphEdge] = []
    for c in citer_rows:
        nodes.append(
            GraphNode(
                case_id=c.id,
                case_name=c.case_name,
                citation=c.citation,
                court=c.court,
                date_filed=c.date_filed.isoformat() if c.date_filed else None,
            )
        )
        t = worst.get(c.id)
        edges.append(
            GraphEdge(
                citing_id=c.id,
                cited_id=case_id,
                treatment=t.type if t else None,
                polarity=_polarity(t.type) if t else "neutral",
                confidence=t.confidence if t else None,
                quote=t.quote if t else None,
                on_other_grounds=bool(t.on_other_grounds) if t else False,
                source_url=_source_url(c.id, c.case_name),
            )
        )

    # Reuse the verdict's signal so /graph and /risk never disagree.
    total_citing = await session.scalar(
        select(func.count()).select_from(CitationEdge).where(CitationEdge.cited_id == case_id)
    )
    citing_treatments = [
        CitingTreatment(
            type=r.type,
            scope=r.scope,
            on_other_grounds=bool(r.on_other_grounds),
            quote=r.quote,
            confidence=r.confidence,
            citing_case_name=None,
            citing_court=None,
            citing_date_filed=None,
        )
        for r in treat_rows
        if r.type
    ]
    # Court/date drive scoring; reload them from the matched citer rows.
    meta = {c.id: c for c in citer_rows}
    for ct, r in zip(citing_treatments, [r for r in treat_rows if r.type]):
        m = meta.get(r.citing_id)
        if m is not None:
            ct.citing_court = m.court
            ct.citing_date_filed = m.date_filed
    verdict = aggregate_risk(
        {
            "case_id": case_id,
            "case_name": focal.case_name,
            "citation": focal.citation,
            "court": focal.court,
            "date_filed": focal_row.date_filed if focal_row else None,
        },
        citing_treatments,
        total_citing=total_citing or 0,
        today=date.today(),
    )

    return GraphResponse(focal=focal, signal=verdict.signal, nodes=nodes, edges=edges)
