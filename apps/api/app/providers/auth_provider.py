"""Authentication provider boundary."""

from typing import Protocol

from app.domain import AuthenticatedUser


class InvalidAccessTokenError(ValueError):
    """Raised when an access token cannot authenticate a user."""


class AuthenticationUnavailableError(RuntimeError):
    """Raised when the identity provider cannot validate a session."""


class AuthenticationProvider(Protocol):
    async def authenticate(self, access_token: str) -> AuthenticatedUser: ...
