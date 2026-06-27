"""GET /cases/{id}/citations — inbound citation edges (the retrieval boundary).

PUBLIC — no JWT, like /resolve and /cases/{id}/risk. Serves the real retrieved
edges from the DB (``citation_edges ⋈ cl_opinions``, populated by
``scripts/ingest_citator.py``); falls back to the Bruen golden stub when nothing is
ingested for the id, so the demo + offline tests still work. An unknown id returns a
200 with an empty edge list (never a 500), so the frontend degrades gracefully. See
``citator.retrieval.load_citations``.
"""

from __future__ import annotations

from fastapi import APIRouter

from htl.citator.retrieval import load_citations
from htl.models.api import CitationsResponse
from htl.routes.dependencies import DbSession

router = APIRouter()


@router.get("/cases/{case_id}/citations", response_model=CitationsResponse)
async def case_citations(case_id: int, session: DbSession) -> CitationsResponse:
    return await load_citations(session, case_id)
