"""Application-owned object-storage boundary."""

from typing import Protocol


class ObjectStorageError(RuntimeError):
    """Raised when an object-storage operation fails."""


class ObjectStorage(Protocol):
    async def upload(
        self,
        path: str,
        content: bytes,
        *,
        content_type: str,
    ) -> None: ...

    async def delete(self, path: str) -> None: ...

    async def download(self, path: str) -> bytes: ...
