from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from app.domain import AuthenticatedUser, Profile, ProfileStatus
from app.providers import (
    AuthenticationUnavailableError,
    InvalidAccessTokenError,
    SupabaseAuthenticationProvider,
)
from app.services import AuthenticationService, SuspendedAccountError

USER = AuthenticatedUser(
    id=UUID("10000000-0000-4000-8000-000000000001"),
    email="alice@example.test",
)


class StubAuthenticationProvider:
    async def authenticate(self, access_token: str) -> AuthenticatedUser:
        assert access_token == "valid-token"
        return USER


class StubProfileRepository:
    def __init__(self, status: ProfileStatus = ProfileStatus.ACTIVE) -> None:
        self.status = status

    async def ensure(self, user: AuthenticatedUser) -> Profile:
        assert user == USER
        now = datetime.now(UTC)
        return Profile(
            user_id=user.id,
            status=self.status,
            created_at=now,
            updated_at=now,
        )


@pytest.mark.asyncio
async def test_authentication_service_accepts_an_active_account() -> None:
    service = AuthenticationService(StubAuthenticationProvider(), StubProfileRepository())

    assert await service.authenticate("valid-token") == USER


@pytest.mark.asyncio
async def test_authentication_service_blocks_a_suspended_account() -> None:
    service = AuthenticationService(
        StubAuthenticationProvider(),
        StubProfileRepository(ProfileStatus.SUSPENDED),
    )

    with pytest.raises(SuspendedAccountError):
        await service.authenticate("valid-token")


@pytest.mark.asyncio
async def test_supabase_provider_validates_a_token_with_auth_server() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "publishable-key"
        assert request.headers["authorization"] == "Bearer valid-token"
        return httpx.Response(200, json={"id": str(USER.id), "email": USER.email})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SupabaseAuthenticationProvider(
            client,
            supabase_url="http://supabase.test",
            publishable_key="publishable-key",
        )

        assert await provider.authenticate("valid-token") == USER


@pytest.mark.asyncio
async def test_supabase_provider_rejects_an_invalid_token_without_leaking_response() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(401, json={"secret": "provider detail"})
        )
    ) as client:
        provider = SupabaseAuthenticationProvider(
            client,
            supabase_url="http://supabase.test",
            publishable_key="publishable-key",
        )

        with pytest.raises(InvalidAccessTokenError, match="invalid or expired") as error:
            await provider.authenticate("bad-token")

    assert "provider detail" not in str(error.value)


@pytest.mark.asyncio
async def test_supabase_provider_reports_auth_server_outages_separately() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(503))
    ) as client:
        provider = SupabaseAuthenticationProvider(
            client,
            supabase_url="http://supabase.test",
            publishable_key="publishable-key",
        )

        with pytest.raises(AuthenticationUnavailableError):
            await provider.authenticate("valid-token")
