"""FastAPI app: lifespan, middleware, exception handlers, routers.

Exception handling: the ``AppError`` and ``RequestValidationError`` handlers run
on the inner exception middleware (inside ``CorrelationIdMiddleware``), so the
correlation ULID is live and gets stamped on their response. The envelope shape
is uniform across both.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from htl import logging_config
from htl.correlation import CORRELATION_ID_HEADER, CorrelationIdMiddleware, get_correlation_id
from htl.db.engine import dispose_engine
from htl.errors import AppError, ValidationFailed
from htl.routes import chat, health, resolve
from htl.settings import settings

_logger = structlog.get_logger("htl.main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logging_config.configure(level=settings.log_level)
    _logger.info("app.startup")
    try:
        yield
    finally:
        await dispose_engine()
        _logger.info("app.shutdown")


async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    cid = get_correlation_id()
    _logger.error("app_error", code=exc.code.value, log_message=exc.log_message)
    return JSONResponse(status_code=exc.status_code, content=exc.to_body(cid))


async def _handle_validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
    error = ValidationFailed("request validation failed")
    return JSONResponse(status_code=error.status_code, content=error.to_body(get_correlation_id()))


app = FastAPI(title="Hack the Law Cambridge 2026 API", lifespan=lifespan)

# CORS first, correlation last → correlation is outermost, so its contextvar is
# live before anything logs and it stamps X-Correlation-ID on every response
# (including the error envelopes). The frontend may read the header back.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[CORRELATION_ID_HEADER],
)
app.add_middleware(CorrelationIdMiddleware)

app.add_exception_handler(AppError, _handle_app_error)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(resolve.router)
