# Parsing and Canonicalization

Phase 4 turns a queued original into application-owned canonical elements and retrieval-ready chunks. Provider-specific output stops at the parser adapter; persistence and later intelligence stages only consume the canonical models.

## Processing flow

```text
queued document and version
        ↓ atomic claim
parsing job (running, attempt + 1)
        ↓
download private original from Supabase Storage
        ↓
Unstructured on-demand job
        ↓
canonical elements
        ↓ section-aware chunking
chunks with page and source-element provenance
        ↓ single database transaction
parsing succeeded + extraction pending
```

New uploads start processing automatically when Unstructured is configured. The upload response remains asynchronous; parsing runs as a lightweight FastAPI background task. This mechanism can later be replaced by a durable queue without changing the parser, canonical models, or frontend API.

## Provider boundary

`DocumentParser` accepts file bytes and returns `ParsedDocument`. `UnstructuredDocumentParser` creates an on-demand workflow job, polls it to a terminal state, downloads the partition output, and converts the response into that application-owned shape.

The adapter uses Unstructured's current on-demand Jobs API with the `hi_res_partition` template by default. Provider job details remain isolated to the adapter, so the application persists only its own canonical models.

Tables retain their text for retrieval and their HTML representation in `structured_content` when Unstructured supplies `text_as_html`. Element hierarchy, page numbers, provider identifiers, and remaining metadata are preserved.

## Chunking

Chunking follows document boundaries rather than fixed offsets:

- a title or heading starts a section;
- following paragraphs and list items stay with that section while they fit;
- tables end their own chunk;
- oversized elements split at word boundaries;
- every chunk stores its page range and source element IDs.

Headers, footers, and image-only elements remain in the canonical document but are excluded from retrieval chunks.

## Idempotency and retries

A database transaction completes the queued stage and atomically claims a pending, failed, or stale parsing job. Only one job can exist for a document version and pipeline stage, so the full stage history remains visible without duplicates. Each parsing claim increments its attempt count, and attempts are bounded by `PROCESSING_MAX_ATTEMPTS`.

Successful persistence replaces that version's elements and chunks in one transaction, then creates the pending extraction stage. Reprocessing therefore cannot append duplicates. Failures record a bounded error message and move the document to `parsing_failed`; calling the process endpoint retries it while attempts remain. Running jobs become reclaimable after `PROCESSING_STALE_AFTER_SECONDS` so an interrupted process does not remain stuck forever.

## Configuration

Add the credentials issued for your Unstructured workspace to `.env`:

```bash
UNSTRUCTURED_API_URL=https://platform.unstructuredapp.io/api/v1
UNSTRUCTURED_API_KEY=replace-with-your-key
UNSTRUCTURED_TEMPLATE_ID=hi_res_partition
UNSTRUCTURED_TIMEOUT_SECONDS=300
UNSTRUCTURED_POLL_INTERVAL_SECONDS=2
```

Then start the local stack normally:

```bash
make db-start
make dev-local
```

Uploading a supported document will queue and parse it. Phase 4 finishes at `extracting`, which represents the pending Phase 5 enrichment stage.

Retry an eligible document manually with:

```http
POST /api/v1/documents/{document_id}/process
```

The automated local integration test uses a deterministic fake parser, so `make db-verify` validates Storage, canonical persistence, provenance, next-stage creation, and idempotency without sending a document to an external service.
