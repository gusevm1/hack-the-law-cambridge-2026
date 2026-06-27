"""POST /cases/{id}/verdict — the use-aware verdict (Feature 5 / C).

PUBLIC — no JWT, like the rest of the citator. Takes the lawyer's intended use (a
proposition-aligned dropdown label) plus optional free-form intent, maps it to the
propositions it depends on (``llm.usemap`` — deterministic for menu picks, model for
free-form), and intersects those with the *compromised* propositions from the
per-proposition verdicts (Contract B, mocked here until Feature 4 lands).

The intersection — real risk *for this use* — is computed in code (``citator.verdict
.compose_verdict``); the model only maps use→propositions, schema-constrained.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from htl.citator.propositions_mock import propositions_for
from htl.citator.verdict import compose_verdict
from htl.llm.usemap import map_use_to_propositions
from htl.models.api import VerdictRequest, VerdictResponse

router = APIRouter()


@router.post("/cases/{case_id}/verdict", response_model=VerdictResponse)
async def case_verdict(case_id: int, req: VerdictRequest) -> VerdictResponse:
    props = propositions_for(case_id, today=date.today())
    mapping = await map_use_to_propositions(req.use, req.intent)
    return compose_verdict(props, mapping)
