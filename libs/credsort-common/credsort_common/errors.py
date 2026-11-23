"""Domain errors and RFC 9457 problem+json responses (ADR-0006)."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .reqctx import request_id


class DomainError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, detail: str = "", *, code: str | None = None, extra: dict | None = None):
        super().__init__(detail)
        self.detail = detail
        if code:
            self.code = code
        self.extra = extra or {}


class Unauthorized(DomainError):
    status, code = 401, "unauthorized"


class Forbidden(DomainError):
    status, code = 403, "forbidden"


class NotFound(DomainError):
    status, code = 404, "not_found"


class Conflict(DomainError):
    status, code = 409, "conflict"


class Gone(DomainError):
    status, code = 410, "gone"


class Unprocessable(DomainError):
    status, code = 422, "unprocessable"


class TooManyAttempts(DomainError):
    status, code = 429, "too_many_attempts"


class UpstreamUnavailable(DomainError):
    status, code = 503, "upstream_unavailable"


class UpstreamHTTPError(DomainError):
    """An upstream service answered with an error status."""
    status, code = 502, "upstream_error"

    def __init__(self, upstream_status: int, detail: str = "", *, problem: dict | None = None):
        super().__init__(detail)
        self.upstream_status = upstream_status
        self.problem = problem or {}


def problem_body(status: int, code: str, title: str, detail: str = "", **extra) -> dict:
    body = {"type": f"https://credsort.ch/problems/{code}", "title": title, "status": status, "code": code,
            "detail": detail, "request_id": request_id()}
    body.update(extra)
    return body


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError):
        return JSONResponse(problem_body(exc.status, exc.code, type(exc).__name__, exc.detail, **exc.extra),
                            status_code=exc.status, media_type="application/problem+json")

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors = [{"loc": [str(p) for p in e["loc"]], "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse(problem_body(422, "validation_error", "Validation error", "Request validation failed", errors=errors),
                            status_code=422, media_type="application/problem+json")
