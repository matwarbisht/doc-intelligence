"""Supabase Storage REST adapter."""

from urllib.parse import quote

import httpx

from app.providers.object_storage import ObjectStorageError


class SupabaseObjectStorage:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        supabase_url: str,
        service_role_key: str,
        bucket: str,
    ) -> None:
        self._client = client
        self._base_url = supabase_url.rstrip("/")
        self._bucket = bucket
        self._headers = {
            "apikey": service_role_key,
            "authorization": f"Bearer {service_role_key}",
        }

    async def upload(
        self,
        path: str,
        content: bytes,
        *,
        content_type: str,
    ) -> None:
        response = await self._client.post(
            self._object_url(path),
            content=content,
            headers={
                **self._headers,
                "content-type": content_type,
                "x-upsert": "false",
            },
        )
        if response.is_error:
            raise ObjectStorageError(f"Supabase upload failed with status {response.status_code}")

    async def delete(self, path: str) -> None:
        response = await self._client.delete(
            self._object_url(path),
            headers=self._headers,
        )
        if response.is_error and response.status_code != 404:
            raise ObjectStorageError(f"Supabase delete failed with status {response.status_code}")

    async def download(self, path: str) -> bytes:
        response = await self._client.get(
            self._object_url(path),
            headers=self._headers,
        )
        if response.is_error:
            raise ObjectStorageError(f"Supabase download failed with status {response.status_code}")
        return response.content

    def _object_url(self, path: str) -> str:
        bucket = quote(self._bucket, safe="")
        object_path = quote(path, safe="/")
        return f"{self._base_url}/storage/v1/object/{bucket}/{object_path}"
