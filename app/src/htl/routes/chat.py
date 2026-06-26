from fastapi import APIRouter

from htl.llm.vertex import generate_reply
from htl.models.api import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    reply = await generate_reply(req.message, [t.model_dump() for t in req.history])
    return ChatResponse(reply=reply)
