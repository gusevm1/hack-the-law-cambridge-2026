"""POST /ask — the flagship: an agentic, citator-aware legal assistant.

PUBLIC — no JWT gate, like /resolve and /cases/{id}/risk. A litigator gives a
free-form case and *how they intend to use it in court*; an agentic Gemini
function-calling loop resolves the case, pulls its risk verdict, and writes a
grounded answer tailored to that use. The loop is MANUAL (not the SDK's automatic
calling) because the tools must be bound to the request's DB session.

The captured resolve/risk objects are returned alongside the prose so the
frontend renders the verdict card from *verified* data, never from the model's
text — the anti-hallucination contract of the citator carries through to /ask.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from google.genai import types

from htl.llm import router as llm_router
from htl.models.api import AskRequest, AskResponse, ResolveRequest
from htl.routes.dependencies import DbSession
from htl.routes.resolve import resolve
from htl.routes.risk import case_risk

router = APIRouter()

MAX_ROUNDS = 5

SYSTEM = (
    "You are a citator specialist assisting a litigator. Your job: determine "
    "whether a case is still good law *for the specific way the lawyer intends to "
    "use it*, and say so in a few grounded sentences.\n\n"
    "Tools — you MUST use them; never assert good-law status from memory:\n"
    "1. Call `resolve_case` with the case the lawyer named to get its CourtListener "
    "id. If it returns found=false, tell the lawyer you cannot verify that case and "
    "stop — do not guess.\n"
    "2. Then call `get_case_risk` with that id to get the citator verdict.\n\n"
    "Only after both tools have run, answer. Tailor the answer to the intended use: "
    "a case that is partially limited or distinguished may be fine to cite as "
    "persuasive authority or to distinguish on the facts, yet unsafe to rely on as "
    "binding/controlling precedent or for a test it once established. State plainly: "
    "the signal (red/amber/green), the overruling case if any (from "
    "ground_truth.overruled_by), and the key negative treatments. Be concise and "
    "practical for someone deciding whether to put this case in a brief. "
    'End every answer with: "General information, not legal advice."'
)

_RESOLVE_TOOL = types.FunctionDeclaration(
    name="resolve_case",
    description=(
        "Resolve a free-form case name or reporter citation to a CourtListener "
        "case id and metadata. Call this first."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "query": types.Schema(
                type=types.Type.STRING,
                description="A case name (e.g. 'Roe v. Wade') or citation (e.g. '410 U.S. 113').",
            )
        },
        required=["query"],
    ),
)

_RISK_TOOL = types.FunctionDeclaration(
    name="get_case_risk",
    description=(
        "Get the citator risk verdict (signal, status, overruling case, negative "
        "treatments) for a CourtListener case id returned by resolve_case."
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

_TOOL = types.Tool(function_declarations=[_RESOLVE_TOOL, _RISK_TOOL])


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest, session: DbSession) -> AskResponse:
    # Captured results from the tool calls — these (not the prose) feed the
    # frontend verdict card, so it always renders verified citator data.
    captured: dict[str, Any] = {"resolve": None, "risk": None}

    async def resolve_case(query: str) -> dict[str, Any]:
        result = await resolve(ResolveRequest(query=query), session)
        captured["resolve"] = result
        return result.model_dump()

    async def get_case_risk(case_id: int) -> dict[str, Any]:
        result = await case_risk(int(case_id), session)
        captured["risk"] = result
        return result.model_dump(mode="json")

    async def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "resolve_case":
            return await resolve_case(str(args.get("query", "")))
        if name == "get_case_risk":
            return await get_case_risk(int(args["case_id"]))
        return {"error": f"unknown tool {name}"}

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM, tools=[_TOOL], temperature=0
    )
    user_prompt = (
        f"Case: {req.case}\n"
        f"Intended use in court: {req.use}\n\n"
        "Is this case still good law for that use? Resolve it, check its risk, "
        "then give a grounded answer for a litigator."
    )
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=user_prompt)])
    ]

    answer = ""
    for _ in range(MAX_ROUNDS):
        # Routed: task "ask" → settings.model_routes["ask"], with model fallback.
        resp = await llm_router.generate("ask", contents=contents, config=config)
        fcs = resp.function_calls or []
        if not fcs:
            answer = resp.text or ""
            break
        # Append the model's function_call turn, then answer each call.
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

    if not answer:
        # Loop exhausted without prose — synthesise a minimal answer from the
        # verified verdict so the response is never empty.
        verdict = captured["risk"]
        if verdict is not None:
            answer = (
                f"Citator signal: {verdict.signal} ({verdict.status}). "
                f"{verdict.risk_rationale} "
                "General information, not legal advice."
            )
        else:
            answer = (
                "I couldn't verify that case against the citator, so I can't "
                "confirm whether it is still good law. General information, not "
                "legal advice."
            )

    return AskResponse(
        answer=answer, resolved_case=captured["resolve"], verdict=captured["risk"]
    )
