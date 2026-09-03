"""Document upload and lifecycle endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.api.dependencies import get_document_service
from app.core.config import get_settings
from app.providers import ObjectStorageError
from app.schemas.documents import DocumentListResponse, DocumentResponse, DocumentUploadResponse
from app.services import (
    DocumentService,
    DocumentUploadError,
    EmptyDocumentError,
    FileTooLargeError,
    UnsupportedDocumentTypeError,
)

router = APIRouter(prefix="/documents")
DocumentServiceDependency = Annotated[DocumentService, Depends(get_document_service)]


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF, DOCX, Markdown, or plain text document")],
    response: Response,
    service: DocumentServiceDependency,
) -> DocumentUploadResponse:
    settings = get_settings()
    content = await file.read(settings.max_upload_bytes + 1)
    await file.close()

    try:
        result = await service.upload(
            filename=file.filename or "",
            content_type=file.content_type,
            content=content,
        )
    except EmptyDocumentError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except FileTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(error),
        ) from error
    except UnsupportedDocumentTypeError as error:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(error),
        ) from error
    except DocumentUploadError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except ObjectStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Document storage is temporarily unavailable.",
        ) from error

    if result.duplicate:
        response.status_code = status.HTTP_200_OK
    return DocumentUploadResponse(
        document=DocumentResponse.from_domain(result.document),
        duplicate=result.duplicate,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    service: DocumentServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    documents = await service.list_documents(limit=limit, offset=offset)
    return DocumentListResponse(
        items=[DocumentResponse.from_domain(document) for document in documents],
        limit=limit,
        offset=offset,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    service: DocumentServiceDependency,
) -> DocumentResponse:
    document = await service.get_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return DocumentResponse.from_domain(document)
