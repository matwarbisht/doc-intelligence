"""Document upload and lifecycle endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)

from app.api.dependencies import (
    get_current_user,
    get_document_service,
    get_processing_service,
    get_safeguard_service,
)
from app.core.config import get_settings
from app.domain import AuthenticatedUser
from app.providers import ObjectStorageError
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentProcessResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.services import (
    DocumentProcessor,
    DocumentService,
    DocumentUploadError,
    EmptyDocumentError,
    FileTooLargeError,
    SafeguardService,
    UnsupportedDocumentTypeError,
)

router = APIRouter(prefix="/documents")
DocumentServiceDependency = Annotated[DocumentService, Depends(get_document_service)]
ProcessingServiceDependency = Annotated[
    DocumentProcessor,
    Depends(get_processing_service),
]
CurrentUserDependency = Annotated[AuthenticatedUser, Depends(get_current_user)]
SafeguardServiceDependency = Annotated[SafeguardService, Depends(get_safeguard_service)]


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF, DOCX, Markdown, or plain text document")],
    response: Response,
    request: Request,
    background_tasks: BackgroundTasks,
    service: DocumentServiceDependency,
    current_user: CurrentUserDependency,
    safeguards: SafeguardServiceDependency,
) -> DocumentUploadResponse:
    source_ip = request.client.host if request.client else None
    await safeguards.guard_upload_request(current_user.id, source_ip)
    settings = get_settings()
    content = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    reservation = await safeguards.reserve_upload(current_user.id, source_ip, len(content))

    try:
        result = await service.upload(
            owner_id=current_user.id,
            filename=file.filename or "",
            content_type=file.content_type,
            content=content,
        )
    except EmptyDocumentError as error:
        await safeguards.release_upload(current_user.id, source_ip, reservation)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except FileTooLargeError as error:
        await safeguards.release_upload(current_user.id, source_ip, reservation)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(error),
        ) from error
    except UnsupportedDocumentTypeError as error:
        await safeguards.release_upload(current_user.id, source_ip, reservation)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(error),
        ) from error
    except DocumentUploadError as error:
        await safeguards.release_upload(current_user.id, source_ip, reservation)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except ObjectStorageError as error:
        await safeguards.release_upload(current_user.id, source_ip, reservation)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Document storage is temporarily unavailable.",
        ) from error
    except Exception:
        await safeguards.release_upload(current_user.id, source_ip, reservation)
        raise

    if result.duplicate:
        await safeguards.release_upload(current_user.id, source_ip, reservation)
        response.status_code = status.HTTP_200_OK
    else:
        processing_service = getattr(request.app.state, "processing_service", None)
        if safeguards.processing_enabled() and isinstance(processing_service, DocumentProcessor):
            background_tasks.add_task(
                processing_service.process_document,
                result.document.id,
            )
    return DocumentUploadResponse(
        document=DocumentResponse.from_domain(result.document),
        duplicate=result.duplicate,
    )


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def process_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    service: ProcessingServiceDependency,
    document_service: DocumentServiceDependency,
    current_user: CurrentUserDependency,
    request: Request,
    safeguards: SafeguardServiceDependency,
) -> DocumentProcessResponse:
    document = await document_service.get_document(current_user.id, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    source_ip = request.client.host if request.client else None
    await safeguards.guard_retry(current_user.id, source_ip, document_id)
    background_tasks.add_task(service.process_document, document_id)
    return DocumentProcessResponse(document_id=document_id)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    service: DocumentServiceDependency,
    current_user: CurrentUserDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    documents = await service.list_documents(current_user.id, limit=limit, offset=offset)
    return DocumentListResponse(
        items=[DocumentResponse.from_domain(document) for document in documents],
        limit=limit,
        offset=offset,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: UUID,
    service: DocumentServiceDependency,
    current_user: CurrentUserDependency,
) -> DocumentDetailResponse:
    intelligence = await service.get_document_intelligence(current_user.id, document_id)
    if intelligence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return DocumentDetailResponse.from_intelligence(intelligence)
