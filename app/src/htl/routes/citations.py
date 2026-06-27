"""GET /cases/{id}/citations — inbound citation edges (retrieval STUB).

PUBLIC — no JWT, like /resolve and /cases/{id}/risk. Serves the contract-true
golden set (Bruen today) so the downstream triage stage can be built against real
data before the retrieval engine is wired. DB-independent. An unknown id returns a
200 with an empty edge list (never a 500), so the frontend degrades gracefully.
"""

from __future__ import annotations

from fastapi import APIRouter

from htl.citator.golden import CITATIONS
from htl.models.api import CaseRef, CitationsResponse

router = APIRouter()


@router.get("/cases/{case_id}/citations", response_model=CitationsResponse)
async def case_citations(case_id: int) -> CitationsResponse:
    hit = CITATIONS.get(case_id)
    if hit is not None:
        return hit
    return CitationsResponse(case=CaseRef(case_id=case_id), total=0, edges=[])
