"""Pipeline composition and concurrency tests."""

import asyncio
from uuid import UUID, uuid4

import pytest

from app.services import BoundedDocumentProcessor, ProcessingResult


class TrackingProcessor:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def process_document(self, document_id: UUID) -> ProcessingResult:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return ProcessingResult(claimed=True)


@pytest.mark.asyncio
async def test_bounded_processor_limits_concurrent_pipelines() -> None:
    delegate = TrackingProcessor()
    processor = BoundedDocumentProcessor(delegate, max_concurrency=2)

    await asyncio.gather(*(processor.process_document(uuid4()) for _ in range(6)))

    assert delegate.max_active == 2
