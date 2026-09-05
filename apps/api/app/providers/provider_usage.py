"""Application-owned boundary for provider attempt admission and accounting."""

from typing import Protocol
from uuid import UUID


class ProviderUsageGuard(Protocol):
    async def before_provider_attempt(
        self,
        *,
        user_id: UUID,
        provider: str,
        operation: str,
    ) -> None: ...

    async def after_provider_attempt(
        self,
        *,
        user_id: UUID,
        provider: str,
        operation: str,
        status_code: int | None,
        succeeded: bool,
    ) -> None: ...
