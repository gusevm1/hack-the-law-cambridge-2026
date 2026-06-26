from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatTurn] = []


class ChatResponse(BaseModel):
    reply: str
