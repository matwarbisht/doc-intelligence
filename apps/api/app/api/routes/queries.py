"""Cross-document query and cited-answer endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import (
    get_current_user,
    get_document_service,
    get_query_service,
    get_safeguard_service,
)
from app.domain import AuthenticatedUser
from app.providers import AnswerGeneratorError, EmbeddingProviderError
from app.schemas.queries import CorpusQueryRequest, CorpusQueryResponse
from app.services import (
    CorpusQueryService,
    DocumentService,
    EmptyQueryError,
    QueryServiceError,
    SafeguardService,
)

router = APIRouter(prefix="/query")
QueryServiceDependency = Annotated[CorpusQueryService, Depends(get_query_service)]
CurrentUserDependency = Annotated[AuthenticatedUser, Depends(get_current_user)]
DocumentServiceDependency = Annotated[DocumentService, Depends(get_document_service)]
SafeguardServiceDependency = Annotated[SafeguardService, Depends(get_safeguard_service)]


@router.post("", response_model=CorpusQueryResponse)
async def query_corpus(
    payload: CorpusQueryRequest,
    service: QueryServiceDependency,
    document_service: DocumentServiceDependency,
    current_user: CurrentUserDependency,
    request: Request,
    safeguards: SafeguardServiceDependency,
) -> CorpusQueryResponse:
    if payload.document_id is not None:
        document = await document_service.get_document(current_user.id, payload.document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )
    source_ip = request.client.host if request.client else None
    await safeguards.guard_ask(current_user.id, source_ip)
    try:
        result = await service.query(
            payload.query,
            user_id=current_user.id,
            document_id=payload.document_id,
        )
    except EmptyQueryError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except (QueryServiceError, AnswerGeneratorError, EmbeddingProviderError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The document corpus could not be queried right now.",
        ) from error
    return CorpusQueryResponse.from_domain(result)
