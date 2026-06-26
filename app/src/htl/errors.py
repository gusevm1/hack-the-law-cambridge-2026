"""Error envelope + the handful of app errors we actually raise.

Every error the API returns has one shape — ``{"error": {code, message,
correlation_id}}`` — so a client (and our logs) can key off ``code`` and trace
by ``correlation_id``. ``log_message`` (server-side, may carry internals) is
kept separate from ``message`` (returned verbatim, safe to show a user).
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    validation_failed = "validation_failed"
    unauthorized = "unauthorized"
    internal_error = "internal_error"


DEFAULT_USER_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.validation_failed: "The request was invalid.",
    ErrorCode.unauthorized: "Authentication is required.",
    ErrorCode.internal_error: "An unexpected error occurred.",
}


class AppError(Exception):
    """Base for errors that map to the envelope. Subclasses set code + status."""

    code: ErrorCode = ErrorCode.internal_error
    status_code: int = 500

    def __init__(self, log_message: str, *, user_message: str | None = None) -> None:
        super().__init__(log_message)
        self.log_message = log_message
        self.user_message = user_message or DEFAULT_USER_MESSAGES[self.code]

    def to_body(self, correlation_id: str) -> dict[str, dict[str, str]]:
        return {
            "error": {
                "code": self.code.value,
                "message": self.user_message,
                "correlation_id": correlation_id,
            }
        }


class ValidationFailed(AppError):
    code = ErrorCode.validation_failed
    status_code = 422


class Unauthorized(AppError):
    code = ErrorCode.unauthorized
    status_code = 401


class InternalError(AppError):
    code = ErrorCode.internal_error
    status_code = 500
