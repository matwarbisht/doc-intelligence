"""Stable HTTP mappings for application-level safeguard failures."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.services import SafeguardViolation


async def safeguard_violation_handler(_request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, SafeguardViolation):
        raise error
    payload: dict[str, object] = {"detail": error.detail, "code": error.code}
    headers: dict[str, str] = {}
    if error.retry_after_seconds is not None:
        payload["retry_after_seconds"] = error.retry_after_seconds
        headers["Retry-After"] = str(error.retry_after_seconds)
    return JSONResponse(status_code=error.status_code, content=payload, headers=headers)
