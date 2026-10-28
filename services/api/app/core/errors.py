"""Lỗi nghiệp vụ chuẩn hoá → JSON {error: {code, message, details}}."""
from typing import Any


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details


class NotFound(AppError):
    status_code = 404
    code = "NOT_FOUND"


class Forbidden(AppError):
    status_code = 403
    code = "FORBIDDEN"


class Unauthorized(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class Conflict(AppError):
    status_code = 409
    code = "CONFLICT"


class ValidationFailed(AppError):
    status_code = 422
    code = "VALIDATION_FAILED"


class InvalidTransition(AppError):
    status_code = 409
    code = "INVALID_TRANSITION"


class BudgetExceeded(AppError):
    status_code = 402
    code = "BUDGET_EXCEEDED"


class ProviderUnavailable(AppError):
    status_code = 503
    code = "PROVIDER_UNAVAILABLE"


class RateLimited(AppError):
    status_code = 429
    code = "RATE_LIMITED"
