"""Supabase Auth adapter using authoritative access-token validation."""

from collections.abc import Mapping
from typing import cast
from uuid import UUID

import httpx

from app.domain import AuthenticatedUser
from app.providers.auth_provider import AuthenticationUnavailableError, InvalidAccessTokenError


class SupabaseAuthenticationProvider:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        supabase_url: str,
        publishable_key: str,
    ) -> None:
        self._client = client
        self._user_url = f"{supabase_url.rstrip('/')}/auth/v1/user"
        self._publishable_key = publishable_key

    async def authenticate(self, access_token: str) -> AuthenticatedUser:
        try:
            response = await self._client.get(
                self._user_url,
                headers={
                    "apikey": self._publishable_key,
                    "authorization": f"Bearer {access_token}",
                },
            )
        except httpx.HTTPError as error:
            raise AuthenticationUnavailableError(
                "Authentication is temporarily unavailable."
            ) from error

        if response.status_code >= 500:
            raise AuthenticationUnavailableError("Authentication is temporarily unavailable.")
        if response.status_code != 200:
            raise InvalidAccessTokenError("The access token is invalid or expired.")

        raw_payload: object = response.json()
        if not isinstance(raw_payload, Mapping):
            raise InvalidAccessTokenError("The authentication response is invalid.")
        payload = cast(Mapping[str, object], raw_payload)
        try:
            user_id = UUID(str(payload["id"]))
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidAccessTokenError("The authentication response is invalid.") from error
        email = payload.get("email")
        return AuthenticatedUser(
            id=user_id,
            email=email if isinstance(email, str) else None,
        )
