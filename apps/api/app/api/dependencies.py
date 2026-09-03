"""FastAPI dependency accessors."""

from typing import cast

from fastapi import HTTPException, Request, status

from app.services import DocumentService


def get_document_service(request: Request) -> DocumentService:
    service = cast(DocumentService | None, getattr(request.app.state, "document_service", None))
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is not configured.",
        )
    return service
