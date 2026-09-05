"""Operational logging tests."""

import json
import logging

from app.core.logging import JsonFormatter, request_id_context


def test_json_formatter_emits_correlation_and_allowlisted_context() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.processing",
        level=logging.INFO,
        pathname=__file__,
        lineno=12,
        msg="Stage completed",
        args=(),
        exc_info=None,
    )
    record.event = "document.stage.completed"
    record.document_id = "00000000-0000-0000-0000-000000000001"
    record.secret = "must-not-be-serialized"

    token = request_id_context.set("request-123")
    try:
        payload = json.loads(formatter.format(record))
    finally:
        request_id_context.reset(token)

    assert payload["level"] == "info"
    assert payload["request_id"] == "request-123"
    assert payload["event"] == "document.stage.completed"
    assert payload["document_id"] == "00000000-0000-0000-0000-000000000001"
    assert "secret" not in payload
