"""GET /cases/{id}/risk — the citator verdict for a case.

PUBLIC — no JWT gate, like /resolve (read-only public legal lookup). ``id`` is a
CourtListener cluster id (== ``cl_opinions.id`` == ``citation_edges.cited_id``),
i.e. what /resolve returns. Loads the inbound treatments + citing metadata and
hands them to the pure ``aggregate_risk``. A case with no edges/treatments yields
a 200 with ``status="unknown"`` — never a 500.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from sqlalchemy import func, select

from htl.citator.risk import CitingTreatment, aggregate_risk
from htl.db.citator import CitationEdge, ClOpinion, Treatment
from htl.models.api import RiskResponse
from htl.routes.dependencies import DbSession

router = APIRouter()


@router.get("/cases/{case_id}/risk", response_model=RiskResponse)
async def case_risk(case_id: int, session: DbSession) -> RiskResponse:
    case_row = (
        await session.execute(select(ClOpinion).where(ClOpinion.id == case_id))
    ).scalars().first()
    case_meta = {
        "case_id": case_id,
        "case_name": case_row.case_name if case_row else None,
        "citation": case_row.citation if case_row else None,
        "court": case_row.court if case_row else None,
        "date_filed": case_row.date_filed if case_row else None,
    }

    total_citing = await session.scalar(
        select(func.count()).select_from(CitationEdge).where(CitationEdge.cited_id == case_id)
    )

    rows = (
        await session.execute(
            select(
                Treatment.type,
                Treatment.scope,
                Treatment.on_other_grounds,
                Treatment.quote,
                Treatment.confidence,
                ClOpinion.case_name,
                ClOpinion.court,
                ClOpinion.date_filed,
            )
            .join(ClOpinion, ClOpinion.id == Treatment.citing_id)
            .where(Treatment.cited_id == case_id)
        )
    ).all()

    treatments = [
        CitingTreatment(
            type=r.type,
            scope=r.scope,
            on_other_grounds=bool(r.on_other_grounds),
            quote=r.quote,
            confidence=r.confidence,
            citing_case_name=r.case_name,
            citing_court=r.court,
            citing_date_filed=r.date_filed,
        )
        for r in rows
        if r.type
    ]

    return aggregate_risk(
        case_meta, treatments, total_citing=total_citing or 0, today=date.today()
    )
