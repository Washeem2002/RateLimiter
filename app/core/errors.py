from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.headers = headers or {}


class NotFoundError(AppError):
    def __init__(self, message: str = "resource not found") -> None:
        super().__init__("not_found", message, status_code=404)


class GoneError(AppError):
    def __init__(self, message: str = "resource expired") -> None:
        super().__init__("gone", message, status_code=410)


class ConflictError(AppError):
    def __init__(self, message: str = "resource already exists") -> None:
        super().__init__("conflict", message, status_code=409)


class ValidationAppError(AppError):
    def __init__(self, message: str = "invalid input") -> None:
        super().__init__("validation_error", message, status_code=422)


class RateLimitError(AppError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(
            "rate_limited",
            "too many requests",
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )


def error_body(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message),
        headers=exc.headers,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_body("internal_error", "an unexpected error occurred"),
    )
