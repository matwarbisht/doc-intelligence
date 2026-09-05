"""Structured application logging and request correlation."""

import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
_EXTRA_FIELDS = (
    "event",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "document_id",
    "stage",
    "outcome",
    "keyword_hits",
    "semantic_hits",
    "structured_hits",
    "fused_hits",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_context.get()
        if request_id:
            payload["request_id"] = request_id
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(*, level: str, json_logs: bool) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter()
        if json_logs
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


async def log_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request_id = _request_id(request.headers.get("x-request-id"))
    token: Token[str | None] = request_id_context.set(request_id)
    started = perf_counter()
    logger = logging.getLogger("app.http")
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Request failed",
            extra={
                "event": "http.request.failed",
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round((perf_counter() - started) * 1_000, 2),
            },
        )
        raise
    else:
        response.headers["x-request-id"] = request_id
        logger.info(
            "Request completed",
            extra={
                "event": "http.request.completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1_000, 2),
            },
        )
        return response
    finally:
        request_id_context.reset(token)


def _request_id(candidate: str | None) -> str:
    if candidate and 1 <= len(candidate) <= 100 and candidate.isascii():
        return candidate
    return str(uuid4())
