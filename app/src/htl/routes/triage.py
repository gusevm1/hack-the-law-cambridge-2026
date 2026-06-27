"""GET /cases/{id}/triage — tier inbound edges by depth of analysis.

PUBLIC — no JWT, like /resolve and /cases/{id}/risk. Pulls the retrieved edges from
the DB (``citator.retrieval.load_citations``; golden fallback offline) and hands them
to the pure ``tier_edges``. Deterministic keyword/metadata only — no LLM. NEVER drops:
noise comes back as ``mention``, surfaced and low-ranked.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from htl.citator.retrieval import load_citations
from htl.citator.triage import tier_edges
from htl.models.api import TriageResponse
from htl.routes.dependencies import DbSession

router = APIRouter()


@router.get("/cases/{case_id}/triage", response_model=TriageResponse)
async def case_triage(case_id: int, session: DbSession) -> TriageResponse:
    cites = await load_citations(session, case_id)
    return tier_edges(cites.case, cites.edges, today=date.today())
