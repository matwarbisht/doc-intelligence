"""FastAPI dependency accessors."""

from typing import cast

from fastapi import HTTPException, Request, status

from app.services import (
    CorpusQueryService,
    DocumentProcessor,
    DocumentService,
)


def get_document_service(request: Request) -> DocumentService:
    service = cast(DocumentService | None, getattr(request.app.state, "document_service", None))
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is not configured.",
        )
    return service


def get_processing_service(
    request: Request,
) -> DocumentProcessor:
    service = cast(
        DocumentProcessor | None,
        getattr(request.app.state, "processing_service", None),
    )
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document parsing is not configured.",
        )
    return service


def get_query_service(request: Request) -> CorpusQueryService:
    service = cast(CorpusQueryService | None, getattr(request.app.state, "query_service", None))
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Corpus querying is not configured.",
        )
    return service
