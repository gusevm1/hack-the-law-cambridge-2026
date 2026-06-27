"""GET /cases/{id}/classify — per-edge, proposition-level treatment (Feature 2).

PUBLIC — no JWT, like the rest of the citator. Triages first (Feature 1), then runs
the LLM **only on the deep + shallow edges** the filter deemed worth it; ``mention``
edges pass through unclassified (the filter already judged them noise). The model
reads + proposes (treatment / proposition / attribution / verbatim quote); the quote
is verified against the passage; code assembles the response.

On Cloud Run the runtime SA reaches Vertex and real Gemini runs; from a laptop the
sandbox blocks Vertex `predict` for the user identity, so `classify_edge` falls back
to the deterministic keyword classifier (tagged `model="keyword-fallback"`).
"""

from __future__ import annotations

import asyncio
from datetime import date

from fastapi import APIRouter

from htl.citator.golden import CITATIONS
from htl.citator.triage import tier_edges
from htl.llm.classify import EdgeClass, classify_edge
from htl.models.api import CaseRef, ClassifiedEdge, ClassifyResponse, EdgeClassification

router = APIRouter()

_CLASSIFY_TIERS = {"deep", "shallow"}


def _to_model(c: EdgeClass) -> EdgeClassification:
    return EdgeClassification(
        treatment=c.treatment,
        proposition=c.proposition,
        holding_vs_dicta=c.holding_vs_dicta,
        attribution=c.attribution,
        quote=c.quote,
        confidence=c.confidence,
        model=c.model,
    )


@router.get("/cases/{case_id}/classify", response_model=ClassifyResponse)
async def case_classify(case_id: int) -> ClassifyResponse:
    hit = CITATIONS.get(case_id)
    case = hit.case if hit is not None else CaseRef(case_id=case_id)
    edges = hit.edges if hit is not None else []
    triage = tier_edges(case, edges, today=date.today())

    async def _maybe(e: object) -> EdgeClass | None:
        if e.tier not in _CLASSIFY_TIERS:
            return None
        return await classify_edge(
            e.passage, case.case_name, case.citation, e.signals.propositions_engaged
        )

    # ponytail: classify the worth-it edges concurrently (≈ deep+shallow per case).
    results = await asyncio.gather(*[_maybe(e) for e in triage.edges])

    classified_edges = [
        ClassifiedEdge(**e.model_dump(), classification=_to_model(c) if c else None)
        for e, c in zip(triage.edges, results, strict=True)
    ]
    return ClassifyResponse(
        case=case,
        total=triage.total,
        counts=triage.counts,
        classified=sum(1 for c in results if c is not None),
        edges=classified_edges,
    )
