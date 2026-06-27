"""GET /cases/{id}/propositions — per-proposition evolution + risk (Feature 4 / B).

PUBLIC — no JWT, like the rest of the citator. Consumes the deep analyzer's findings
(Contract A; mocked by ``golden_analysis.analyze`` until Feature 3 lands), buckets
them by proposition, and returns the per-proposition verdict + the composed operative
rule. All deterministic — risk, splits, and cert are code/curated-grounded; no LLM.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from htl.citator.certwatch import CERT_WATCH
from htl.citator.evolution import aggregate_propositions, findings_from_edges
from htl.citator.golden_analysis import analyze
from htl.models.api import CaseRef, PropositionsResponse

router = APIRouter()


@router.get("/cases/{case_id}/propositions", response_model=PropositionsResponse)
async def case_propositions(case_id: int) -> PropositionsResponse:
    today = date.today()
    # ponytail: mock of Feature 3's /analyze; swap for the real AnalyzeResponse once it ships.
    analyzed = analyze(case_id, today=today)
    if analyzed is None:
        return PropositionsResponse(
            case=CaseRef(case_id=case_id),
            operative_rule="Unknown — no analysis on record for this case.",
            propositions=[],
            as_of=today.isoformat(),
        )
    findings = findings_from_edges(analyzed.edges)
    return aggregate_propositions(analyzed.case, findings, cert_table=CERT_WATCH, today=today)
