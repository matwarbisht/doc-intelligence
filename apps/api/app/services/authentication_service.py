"""Authentication and application-account policy."""

from app.domain import AuthenticatedUser, ProfileStatus
from app.providers import AuthenticationProvider
from app.repositories import ProfileRepository


class SuspendedAccountError(PermissionError):
    """Raised when an authenticated account is not allowed to use the application."""


class AuthenticationService:
    def __init__(
        self,
        provider: AuthenticationProvider,
        profiles: ProfileRepository,
    ) -> None:
        self._provider = provider
        self._profiles = profiles

    async def authenticate(self, access_token: str) -> AuthenticatedUser:
        user = await self._provider.authenticate(access_token)
        profile = await self._profiles.ensure(user)
        if profile.status is ProfileStatus.SUSPENDED:
            raise SuspendedAccountError("This account has been suspended.")
        return user
