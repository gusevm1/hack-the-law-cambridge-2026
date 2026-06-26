"""structlog → JSON lines on stdout (Cloud Run ships stdout to Cloud Logging).

``configure`` is idempotent (structlog replaces global state) and called once
from the app lifespan. The ``_add_correlation_id`` processor pulls the current
request's ULID off the contextvar so every log line is correlated without the
call site passing it around.
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.typing import EventDict, WrappedLogger

from htl.correlation import correlation_id


def _add_correlation_id(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    cid = correlation_id.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def configure(*, level: str = "INFO") -> None:
    log_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            _add_correlation_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
