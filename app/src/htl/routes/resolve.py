"""POST /resolve — open-citator lookup: a citation or case name → a CourtListener
*cluster id* (the id space of ``citation_edges.cited_id``), so the result can feed
``GET /cases/{id}/risk`` later.

PUBLIC — intentionally no JWT gate. This is a read-only public legal lookup and
accessibility is a product goal; ``/chat`` is gated, this one deliberately is not.

Resolution order: (1) local DB — exact citation, else case-insensitive case name;
(2) fall back to CourtListener's v4 *search* endpoint, which works with NO token.
ponytail: CL's ``citation-lookup`` endpoint would give stronger verification but
needs a token — we use unauth ``search`` + the local DB for now.
"""

from __future__ import annotations

import asyncio
import urllib.parse
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from htl.citator.cl_client import cl_get_json
from htl.db.citator import ClOpinion
from htl.models.api import ResolveRequest, ResolveResponse
from htl.routes.dependencies import DbSession

router = APIRouter()

CL_SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"


def cl_search(query: str) -> dict[str, Any]:
    """Unauthenticated CourtListener v4 SCOTUS search, through the single-flight
    paced client (so it can't race ingest against the rate limit). Blocking — the
    route calls it via ``asyncio.to_thread``."""
    params = {"q": query, "court": "scotus", "type": "o"}
    url = CL_SEARCH_URL + "?" + urllib.parse.urlencode(params)
    return cl_get_json(url)


def _pick_citation(cit: Any) -> str | None:
    """One citation string, preferring the official U.S. Reports cite."""
    if isinstance(cit, str):
        return cit or None
    if not cit:
        return None
    for c in cit:
        if " U.S. " in c:
            return c
    return cit[0]


def _is_strong(result: dict[str, Any], query: str) -> bool:
    """Strong hit: the query equals one of the result's citations, or is contained
    (case-insensitively) in its case name."""
    if query in (result.get("citation") or []):
        return True
    return query.lower() in (result.get("caseName") or "").lower()


@router.post("/resolve", response_model=ResolveResponse)
async def resolve(req: ResolveRequest, session: DbSession) -> ResolveResponse:
    query = req.query.strip()

    # (1) Local DB — exact citation, else case-insensitive case name.
    result = await session.execute(
        select(ClOpinion).where(ClOpinion.citation == query).limit(1)
    )
    row = result.scalars().first()
    if row is None:
        result = await session.execute(
            select(ClOpinion).where(ClOpinion.case_name.ilike(query)).limit(1)
        )
        row = result.scalars().first()
    if row is not None:
        return ResolveResponse(
            found=True,
            case_id=row.id,  # ClOpinion.id == CL cluster id (== citation_edges.cited_id)
            case_name=row.case_name,
            citation=row.citation,
            court=row.court,
            date_filed=row.date_filed.isoformat() if row.date_filed else None,
            source="local",
        )

    # (2) Fallback — CourtListener search (unauth). Run blocking urllib off the loop.
    try:
        data = await asyncio.to_thread(cl_search, query)
    except Exception:  # network/parse failure → no match (never a hallucinated case)
        return ResolveResponse(found=False)

    results = data.get("results") or []
    top = results[0] if results else None
    if not top or top.get("cluster_id") is None:
        return ResolveResponse(found=False)

    strong_ids = {r.get("cluster_id") for r in results if _is_strong(r, query)}
    return ResolveResponse(
        found=True,
        case_id=top["cluster_id"],  # CL cluster id — feeds /cases/{id}/risk
        case_name=top.get("caseName"),
        citation=_pick_citation(top.get("citation")),
        court=top.get("court_id"),
        date_filed=(top.get("dateFiled") or "")[:10] or None,
        source="cl_search",
        ambiguous=len(strong_ids) > 1,
    )
