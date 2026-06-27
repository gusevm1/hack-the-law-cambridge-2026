"""POST /chat — the citator-aware conversational assistant.

PUBLIC (like /ask, /resolve, /risk): no JWT. A multi-turn chat that grounds every
answer in the citator's source graph. Two modes, by request shape:

- GLOBAL (no ``case_id``) — doctrinal questions across the graph: "What is the
  current test under Bruen?", "How has Rahimi been treated since 2024?". The model
  resolves the case(s) it needs and reads their proposition evolution.
- CASE-SCOPED (``case_id`` set) — the analysis page's chat. That case's proposition
  analysis is pre-loaded into context so follow-ups about *this* case answer at once.

Like /ask, the function-calling loop is MANUAL so the tools bind to the request's
DB session. The reply is grounded in resolve/risk/propositions tool results — the
model is told never to assert good-law status or doctrinal evolution from memory.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from google.genai import types

from htl.llm import router as llm_router
from htl.models.api import ChatRequest, ChatResponse, ResolveRequest
from htl.routes.ask import _RESOLVE_TOOL, _RISK_TOOL
from htl.routes.dependencies import DbSession
from htl.routes.propositions import case_propositions
from htl.routes.resolve import resolve
from htl.routes.risk import case_risk

router = APIRouter()

MAX_ROUNDS = 6

SYSTEM = (
    "You are a citator specialist talking with a litigator about whether cases are "
    "still good law and how the governing doctrine has evolved. Ground everything in "
    "the citator's source graph — never assert good-law status or how a line of cases "
    "developed from memory.\n\n"
    "Tools (use them; chain as many as the question needs):\n"
    "- `resolve_case(query)` — a case name or citation → its CourtListener id. Call "
    "this first for any case the user names. If found=false, say you can't verify it "
    "and stop guessing about it.\n"
    "- `get_case_risk(case_id)` — the citator verdict (signal, overruling case, "
    "negative treatments).\n"
    "- `get_case_propositions(case_id)` — the case broken into its propositions, each "
    "with how it evolved through later decisions (treatment, timeline, what changed) "
    "plus the composed operative rule. This is what you read to explain the CURRENT "
    "test and how a precedent has been treated over time.\n\n"
    "Answering: for a doctrinal question (the current test, how a case has been "
    "treated), resolve the anchor case, read its propositions, and synthesise the "
    "evolution — name the cases that moved the rule and what each changed, then state "
    "the rule as it stands now. Be specific and practical, a few tight sentences or "
    "short bullets, no preamble. Only claim what the graph supports; if the graph "
    "doesn't cover something, say so rather than inventing it. "
    'End every answer with: "General information, not legal advice."'
)

_PROPS_TOOL = types.FunctionDeclaration(
    name="get_case_propositions",
    description=(
        "Get the case's proposition-level analysis: each proposition's treatment, "
        "evolution timeline, and what changed, plus the composed operative rule. Use "
        "this to explain the current test or how a precedent has been treated over time."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "case_id": types.Schema(
                type=types.Type.INTEGER,
                description="The CourtListener case id from resolve_case.",
            )
        },
        required=["case_id"],
    ),
)

_TOOL = types.Tool(function_declarations=[_RESOLVE_TOOL, _RISK_TOOL, _PROPS_TOOL])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, session: DbSession) -> ChatResponse:
    async def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "resolve_case":
            r = await resolve(ResolveRequest(query=str(args.get("query", ""))), session)
            return r.model_dump()
        if name == "get_case_risk":
            r = await case_risk(int(args["case_id"]), session)
            return r.model_dump(mode="json")
        if name == "get_case_propositions":
            r = await case_propositions(int(args["case_id"]))
            return r.model_dump(mode="json")
        return {"error": f"unknown tool {name}"}

    # Replay the conversation so far, then the new message.
    contents: list[types.Content] = [
        types.Content(
            role="user" if t.role == "user" else "model",
            parts=[types.Part(text=t.content)],
        )
        for t in req.history
    ]

    # Case-scoped chat: pre-load this case's propositions so follow-ups are grounded
    # without a round-trip (the model can still resolve other cases via the tools).
    if req.case_id is not None:
        props = await case_propositions(req.case_id)
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=(
                            "Context — the case on screen is "
                            f"{props.case.case_name or req.case_id} (id {req.case_id}). "
                            "Its proposition analysis (use for follow-ups about this "
                            f"case):\n{json.dumps(props.model_dump(mode='json'))}"
                        )
                    )
                ],
            )
        )

    contents.append(types.Content(role="user", parts=[types.Part(text=req.message)]))

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM, tools=[_TOOL], temperature=0
    )

    reply = ""
    for _ in range(MAX_ROUNDS):
        resp = await llm_router.generate("chat", contents=contents, config=config)
        fcs = resp.function_calls or []
        if not fcs:
            reply = resp.text or ""
            break
        contents.append(resp.candidates[0].content)
        for fc in fcs:
            result = await dispatch(fc.name or "", dict(fc.args or {}))
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=fc.name, response={"result": result}
                            )
                        )
                    ],
                )
            )

    if not reply:
        reply = (
            "I couldn't pull enough from the citator to answer that confidently. "
            "Try naming a specific case. General information, not legal advice."
        )
    return ChatResponse(reply=reply)
