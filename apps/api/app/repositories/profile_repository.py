"""Persistence boundary for authenticated application profiles."""

from typing import Protocol

from app.domain import AuthenticatedUser, Profile


class ProfileRepository(Protocol):
    async def ensure(self, user: AuthenticatedUser) -> Profile: ...
