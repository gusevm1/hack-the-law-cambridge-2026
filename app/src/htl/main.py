from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from htl.routes import chat, health
from htl.settings import settings

app = FastAPI(title="Hack the Law Cambridge 2026 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
