from fastapi import APIRouter

from htl.correlation import get_correlation_id
from htl.db import repositories
from htl.llm.vertex import generate_reply
from htl.models.api import ChatRequest, ChatResponse
from htl.routes.dependencies import CurrentUser, DbSession

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user: CurrentUser, session: DbSession) -> ChatResponse:
    cid = get_correlation_id()
    reply = await generate_reply(req.message, [t.model_dump() for t in req.history])
    # Persist both turns, stamped with the caller + this request's correlation id.
    await repositories.add_message(
        session, user_id=user.user_id, role="user", content=req.message, correlation_id=cid
    )
    await repositories.add_message(
        session, user_id=user.user_id, role="assistant", content=reply, correlation_id=cid
    )
    await session.commit()
    return ChatResponse(reply=reply)
