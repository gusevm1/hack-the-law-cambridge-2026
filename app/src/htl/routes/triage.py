"""GET /cases/{id}/triage — tier inbound edges by depth of analysis.

PUBLIC — no JWT, like /resolve and /cases/{id}/risk. Pulls the retrieved edges
(the citations stub today; the retrieval engine later) and hands them to the pure
``tier_edges``. Deterministic keyword/metadata only — no LLM, no DB. NEVER drops:
noise comes back as ``mention``, surfaced and low-ranked.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from htl.citator.golden import CITATIONS
from htl.citator.triage import tier_edges
from htl.models.api import CaseRef, TriageResponse

router = APIRouter()


@router.get("/cases/{case_id}/triage", response_model=TriageResponse)
async def case_triage(case_id: int) -> TriageResponse:
    hit = CITATIONS.get(case_id)
    case = hit.case if hit is not None else CaseRef(case_id=case_id)
    edges = hit.edges if hit is not None else []
    return tier_edges(case, edges, today=date.today())
