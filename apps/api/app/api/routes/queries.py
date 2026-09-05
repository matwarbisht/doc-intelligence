"""Cross-document query and cited-answer endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_query_service
from app.providers import AnswerGeneratorError, EmbeddingProviderError
from app.schemas.queries import CorpusQueryRequest, CorpusQueryResponse
from app.services import CorpusQueryService, EmptyQueryError, QueryServiceError

router = APIRouter(prefix="/query")
QueryServiceDependency = Annotated[CorpusQueryService, Depends(get_query_service)]


@router.post("", response_model=CorpusQueryResponse)
async def query_corpus(
    payload: CorpusQueryRequest,
    service: QueryServiceDependency,
) -> CorpusQueryResponse:
    try:
        result = await service.query(payload.query, document_id=payload.document_id)
    except EmptyQueryError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except (QueryServiceError, AnswerGeneratorError, EmbeddingProviderError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The document corpus could not be queried right now.",
        ) from error
    return CorpusQueryResponse.from_domain(result)
