import json

import httpx
import pytest

from app.providers import DocumentParserError, UnstructuredDocumentParser


@pytest.mark.asyncio
async def test_unstructured_parser_runs_job_and_maps_elements() -> None:
    poll_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        assert request.headers["unstructured-api-key"] == "test-key"
        if request.method == "POST":
            assert request.url.path == "/api/v1/jobs/"
            assert b'filename="report.pdf"' in request.content
            assert b"hi_res_partition" in request.content
            return httpx.Response(200, json={"id": "job-1", "status": "SCHEDULED"})
        if request.url.path == "/api/v1/jobs/job-1":
            poll_count += 1
            if poll_count == 1:
                return httpx.Response(200, json={"id": "job-1", "status": "IN_PROGRESS"})
            return httpx.Response(
                200,
                json={
                    "id": "job-1",
                    "status": "COMPLETED",
                    "output_node_files": [
                        {
                            "node_id": "partition-node",
                            "file_id": "report-output.json",
                            "node_type": "partition",
                            "node_subtype": "unstructured_api",
                        }
                    ],
                },
            )
        assert request.url.path == "/api/v1/jobs/job-1/download"
        assert request.url.params["file_id"] == "report-output.json"
        assert request.url.params["node_id"] == "partition-node"
        return httpx.Response(
            200,
            json=[
                {
                    "type": "Title",
                    "element_id": "heading-1",
                    "text": "Results",
                    "metadata": {"page_number": 1},
                },
                {
                    "type": "Table",
                    "element_id": "table-1",
                    "text": "Revenue 24%",
                    "metadata": {
                        "page_number": 2,
                        "parent_id": "heading-1",
                        "text_as_html": "<table><tr><td>24%</td></tr></table>",
                    },
                },
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        parser = UnstructuredDocumentParser(
            client,
            api_url="https://parser.example.test/api/v1/",
            api_key="test-key",
            poll_interval_seconds=0,
        )
        parsed = await parser.parse(
            filename="report.pdf",
            content_type="application/pdf",
            content=b"pdf",
        )

    assert poll_count == 2
    assert len(parsed.elements) == 2
    assert parsed.elements[1].parent_provider_id == "heading-1"
    assert parsed.elements[1].structured_content == {"html": "<table><tr><td>24%</td></tr></table>"}


@pytest.mark.asyncio
async def test_unstructured_parser_reports_failed_job() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"id": "job-1", "status": "SCHEDULED"})
        return httpx.Response(200, json={"id": "job-1", "status": "FAILED"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        parser = UnstructuredDocumentParser(
            client,
            api_url="https://parser.example.test/api/v1",
            api_key="test-key",
            poll_interval_seconds=0,
        )
        with pytest.raises(DocumentParserError, match="status FAILED"):
            await parser.parse(
                filename="report.pdf",
                content_type="application/pdf",
                content=b"pdf",
            )


@pytest.mark.asyncio
async def test_unstructured_parser_hides_provider_response_details() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, content=json.dumps({"secret": "provider detail"}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        parser = UnstructuredDocumentParser(
            client,
            api_url="https://parser.example.test/api/v1",
            api_key="bad-key",
        )
        with pytest.raises(DocumentParserError, match="status 401") as caught:
            await parser.parse(
                filename="report.pdf",
                content_type="application/pdf",
                content=b"pdf",
            )

    assert "provider detail" not in str(caught.value)
