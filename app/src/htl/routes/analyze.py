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
from htl.citator.retrieval import load_citations
from htl.citator.triage import tier_edges
from htl.llm.analyze import EdgeAnalysis, analyze_edge
from htl.models.api import (
    AnalyzedEdge,
    AnalyzeResponse,
    PropositionFinding,
    TieredEdge,
)
from htl.routes.dependencies import DbSession

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
async def case_analyze(case_id: int, session: DbSession) -> AnalyzeResponse:
    cites = await load_citations(session, case_id)
    case = cites.case
    triage = tier_edges(case, cites.edges, today=date.today())

    async def _maybe(e: TieredEdge) -> EdgeAnalysis | None:
        if e.tier not in _ANALYZE_TIERS:
            return None
        # Full opinion text when golden persisted it (rich, multi-proposition read),
        # else the DB-stored passage span — analyze_edge lowers to snippet depth when
        # it's only the window. ponytail: when retrieval persists full text per citing
        # id, read it here by id; the golden map stays the offline-demo enrichment.
        text = golden.full_text_for(e.citing_case.case_name) or e.passage
        return await analyze_edge(e, case, text)

    results = await asyncio.gather(*[_maybe(e) for e in triage.edges])

    analyzed_edges = [_to_edge(e, a) for e, a in zip(triage.edges, results, strict=True)]
    return AnalyzeResponse(
        case=case,
        total=triage.total,
        counts=triage.counts,
        analyzed=sum(1 for a in results if a is not None),
        edges=analyzed_edges,
    )
