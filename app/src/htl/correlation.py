"""Per-request correlation id.

A ``ContextVar`` holds a ULID for the duration of each request; any log line
emitted during the request is stamped with it (see ``logging_config``), and the
middleware echoes it on the response so a client can quote it back when
reporting an issue. A well-behaved caller can thread its own id in via the
``X-Correlation-ID`` header — we reuse it only if it is a real ULID, otherwise
we mint a fresh one (stops a client poisoning log/row correlation with junk).

Pure-ASGI (not BaseHTTPMiddleware): we only need to read one inbound header and
inject one outbound header, which is cheaper done by wrapping ``send``.
"""

from __future__ import annotations

from contextvars import ContextVar

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from ulid import ULID

CORRELATION_ID_HEADER = "X-Correlation-ID"

# Default "" means "outside any request scope" — the logging processor omits the
# field rather than emitting a bogus id.
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """The current request's correlation ULID, or ``""`` outside a request."""
    return correlation_id.get()


def _coerce(raw: str | None) -> str:
    if raw:
        try:
            return str(ULID.from_str(raw))
        except ValueError:
            pass
    return str(ULID())


class CorrelationIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        cid = _coerce(Headers(scope=scope).get(CORRELATION_ID_HEADER))
        token = correlation_id.set(cid)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[CORRELATION_ID_HEADER] = cid
            await send(message)

        try:
            # ponytail: a truly-unhandled 500 from Starlette's outer error
            # middleware won't carry this header (it sits outside us). Handled
            # errors (AppError, validation) run inside, so they do. Upgrade
            # path if 500s need the header: catch here and emit the envelope.
            await self.app(scope, receive, send_wrapper)
        finally:
            correlation_id.reset(token)
