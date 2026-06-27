"""GET /cases/{id}/analyze — deep per-case, per-proposition analysis (Feature 3).

PUBLIC — no JWT, like the rest of the citator. Triages first (Feature 1), then deep-
reads **only the deep + shallow edges** the filter deemed worth it; ``mention`` edges
pass through un-analyzed (findings=[]). Each worth-it edge is read at the depth its
source allows: full opinion text when retrieval persisted it (multi-proposition
findings), else the snippet (one finding, lowered confidence). See ``llm.analyze``.

The model reads + proposes; quotes are verified verbatim; code assembles the
response. Fans the (slow) reads out concurrently across edges.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import date

from fastapi import APIRouter

from htl.citator import golden
from htl.citator.triage import tier_edges
from htl.llm.analyze import EdgeAnalysis, analyze_edge
from htl.models.api import (
    AnalyzedEdge,
    AnalyzeResponse,
    CaseRef,
    PropositionFinding,
    TieredEdge,
)

router = APIRouter()

_ANALYZE_TIERS = {"deep", "shallow"}


def _to_edge(e: TieredEdge, a: EdgeAnalysis | None) -> AnalyzedEdge:
    if a is None:  # mention — surfaced but not analyzed
        return AnalyzedEdge(**e.model_dump(), analysis_depth="snippet", findings=[],
                            case_summary="", model="")
    return AnalyzedEdge(
        **e.model_dump(),
        analysis_depth=a.analysis_depth,
        findings=[PropositionFinding(**asdict(f)) for f in a.findings],
        case_summary=a.case_summary,
        model=a.model,
    )


@router.get("/cases/{case_id}/analyze", response_model=AnalyzeResponse)
async def case_analyze(case_id: int) -> AnalyzeResponse:
    hit = golden.CITATIONS.get(case_id)
    case = hit.case if hit is not None else CaseRef(case_id=case_id)
    edges = hit.edges if hit is not None else []
    triage = tier_edges(case, edges, today=date.today())

    async def _maybe(e: TieredEdge) -> EdgeAnalysis | None:
        if e.tier not in _ANALYZE_TIERS:
            return None
        # ponytail: golden.full_text_for mocks the cl_opinions.plain_text lookup the
        # retrieval engine will persist (keyed by citing opinion id). Swap that seam,
        # not this route, when the real data lands.
        return await analyze_edge(e, case, golden.full_text_for(e.citing_case.case_name))

    results = await asyncio.gather(*[_maybe(e) for e in triage.edges])

    analyzed_edges = [_to_edge(e, a) for e, a in zip(triage.edges, results, strict=True)]
    return AnalyzeResponse(
        case=case,
        total=triage.total,
        counts=triage.counts,
        analyzed=sum(1 for a in results if a is not None),
        edges=analyzed_edges,
    )
