"""Adapter for Unstructured on-demand workflow jobs."""

import asyncio
import hashlib
import json
from collections.abc import Mapping
from typing import cast

import httpx

from app.domain import Metadata, StructuredContent
from app.providers.document_parser import (
    DocumentParserError,
    ParsedDocument,
    ParsedElement,
)


class UnstructuredDocumentParser:
    provider_name = "unstructured"
    provider_version = "workflow-jobs-v1"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_url: str,
        api_key: str,
        template_id: str = "hi_res_partition",
        timeout_seconds: float = 300,
        poll_interval_seconds: float = 2,
    ) -> None:
        self._client = client
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._template_id = template_id
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds

    async def parse(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> ParsedDocument:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                job = await self._create_job(
                    filename=filename,
                    content_type=content_type,
                    content=content,
                )
                completed_job = await self._wait_for_job(job)
                payload = await self._download_output(completed_job)
        except TimeoutError as error:
            raise DocumentParserError("Unstructured parsing timed out.") from error

        if not isinstance(payload, list):
            raise DocumentParserError("Unstructured returned an invalid element response.")
        items = cast(list[object], payload)
        elements = tuple(
            self._element(cast(Mapping[object, object], item), ordinal)
            for ordinal, item in enumerate(items)
            if isinstance(item, Mapping)
        )
        if not elements:
            raise DocumentParserError("Unstructured returned no document elements.")
        return ParsedDocument(elements=elements)

    async def _create_job(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> Mapping[object, object]:
        response = await self._request(
            "POST",
            "/jobs/",
            data={"request_data": json.dumps({"template_id": self._template_id, "job_nodes": []})},
            files=[("input_files", (filename, content, content_type))],
        )
        payload = self._json_object(response)
        if not isinstance(payload.get("id"), str):
            raise DocumentParserError("Unstructured returned an invalid job response.")
        return payload

    async def _wait_for_job(self, job: Mapping[object, object]) -> Mapping[object, object]:
        current = job
        job_id = cast(str, job["id"])
        while True:
            status = current.get("status")
            normalized_status = status.upper() if isinstance(status, str) else ""
            if normalized_status == "COMPLETED":
                return current
            if normalized_status in {"FAILED", "STOPPED"}:
                raise DocumentParserError(
                    f"Unstructured parsing job ended with status {normalized_status}."
                )
            if normalized_status not in {"SCHEDULED", "IN_PROGRESS"}:
                raise DocumentParserError("Unstructured returned an invalid job status.")
            await asyncio.sleep(self._poll_interval_seconds)
            response = await self._request("GET", f"/jobs/{job_id}")
            current = self._json_object(response)

    async def _download_output(self, job: Mapping[object, object]) -> object:
        raw_outputs = job.get("output_node_files")
        if not isinstance(raw_outputs, list):
            raise DocumentParserError("Unstructured job did not include an output file.")
        output: Mapping[object, object] | None = None
        for raw_output in cast(list[object], raw_outputs):
            if not isinstance(raw_output, Mapping):
                continue
            candidate = cast(Mapping[object, object], raw_output)
            if (
                candidate.get("node_type") == "partition"
                and isinstance(candidate.get("file_id"), str)
                and isinstance(candidate.get("node_id"), str)
            ):
                output = candidate
                break
        if output is None:
            raise DocumentParserError("Unstructured job did not include partition output.")
        response = await self._request(
            "GET",
            f"/jobs/{job['id']}/download",
            params={
                "file_id": cast(str, output["file_id"]),
                "node_id": cast(str, output["node_id"]),
            },
        )
        try:
            return cast(object, response.json())
        except ValueError as error:
            raise DocumentParserError("Unstructured returned invalid JSON.") from error

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, str] | None = None,
        files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            response = await self._client.request(
                method,
                f"{self._api_url}{path}",
                headers={
                    "accept": "application/json",
                    "unstructured-api-key": self._api_key,
                },
                follow_redirects=True,
                data=data,
                files=files,
                params=params,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPError as error:
            status = (
                error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
            )
            detail = f" with status {status}" if status is not None else ""
            raise DocumentParserError(f"Unstructured request failed{detail}.") from error

    @staticmethod
    def _json_object(response: httpx.Response) -> Mapping[object, object]:
        try:
            payload = cast(object, response.json())
        except ValueError as error:
            raise DocumentParserError("Unstructured returned invalid JSON.") from error
        if not isinstance(payload, Mapping):
            raise DocumentParserError("Unstructured returned an invalid job response.")
        return cast(Mapping[object, object], payload)

    @staticmethod
    def _element(item: Mapping[object, object], ordinal: int) -> ParsedElement:
        raw_metadata = item.get("metadata")
        metadata: Metadata = (
            {str(key): value for key, value in cast(Mapping[object, object], raw_metadata).items()}
            if isinstance(raw_metadata, Mapping)
            else {}
        )
        parent_id = metadata.pop("parent_id", None)
        table_html = metadata.pop("text_as_html", None)
        structured_content: StructuredContent | None = None
        if isinstance(table_html, str) and table_html:
            structured_content = {"html": table_html}

        raw_text = item.get("text")
        text = raw_text.strip() if isinstance(raw_text, str) else None
        raw_category = item.get("type")
        category = raw_category if isinstance(raw_category, str) else "Unknown"
        raw_provider_id = item.get("element_id")
        provider_id = (
            raw_provider_id
            if isinstance(raw_provider_id, str) and raw_provider_id
            else hashlib.sha256(f"{ordinal}:{category}:{text or ''}".encode()).hexdigest()
        )
        raw_page = metadata.get("page_number")
        page_number = raw_page if isinstance(raw_page, int) and raw_page > 0 else None

        return ParsedElement(
            provider_id=provider_id,
            category=category,
            text=text or None,
            page_number=page_number,
            parent_provider_id=parent_id if isinstance(parent_id, str) else None,
            structured_content=structured_content,
            metadata=metadata,
        )
