"""FastAPI dependency accessors."""

from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain import AuthenticatedUser
from app.providers import AuthenticationUnavailableError, InvalidAccessTokenError
from app.services import (
    AuthenticationService,
    CorpusQueryService,
    DocumentProcessor,
    DocumentService,
    SuspendedAccountError,
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_authentication_service(request: Request) -> AuthenticationService:
    service = cast(
        AuthenticationService | None,
        getattr(request.app.state, "authentication_service", None),
    )
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )
    return service


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    service = get_authentication_service(request)
    try:
        return await service.authenticate(credentials.credentials)
    except InvalidAccessTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The session is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except AuthenticationUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable.",
        ) from error
    except SuspendedAccountError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been suspended.",
        ) from error


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
