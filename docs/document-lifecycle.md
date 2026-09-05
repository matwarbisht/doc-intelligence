# Document Upload and Lifecycle

Phase 3 introduces the first product workflow: accepting an original document, storing it privately, and recording its initial asynchronous-processing state.

## Request flow

```text
React document library
        ↓ bounded concurrent multipart/form-data requests
POST /api/v1/documents
        ↓
validate type and 50 MB limit
        ↓
calculate SHA-256 content hash
        ↓
deduplicate by content hash
        ↓
upload original to private Supabase Storage
        ↓
transaction: document + version 1 + queued job
        ↓
return queued document
```

If persistence fails after Storage accepts an object, the service makes a best-effort deletion so an incomplete upload does not normally leave an orphan. A concurrent duplicate is resolved to the existing document.

## API

```text
POST /api/v1/documents                 Upload a document
GET  /api/v1/documents                 List documents, newest first
GET  /api/v1/documents/{document_id}   Retrieve one document
```

The MVP accepts PDF, DOCX, Markdown, and plain-text files. The bucket and application both enforce a 50 MB limit. A new upload returns `201`; uploading identical content returns the existing document with `200` and `duplicate: true`.

The browser supports multi-selection and drag-and-drop, but intentionally sends one
request per file with at most three uploads in flight. Its queue preserves independent
success, duplicate, and failure states so one invalid document cannot fail the batch.
Failed items can be retried and completed items can be cleared without affecting the
document library.

The API wraps its configured parser/enrichment pipeline in a shared semaphore. The
default `PROCESSING_CONCURRENCY=3` limits simultaneous full pipelines across upload
requests while durable database claims preserve retry and idempotency semantics.
Within those pipelines, `UNSTRUCTURED_CONCURRENCY=1` serializes complete parsing jobs
to respect the provider's active-job limit while allowing Gemini work from another
pipeline to overlap. Transient Unstructured network, 429, and selected 5xx failures
are retried with configurable bounded exponential delay.

Responses expose user-facing file metadata and lifecycle status but not internal storage paths, content hashes, or service credentials.

## Local development

Start Supabase, then run both applications with credentials read directly from the local CLI:

```bash
make db-start
make dev-local
```

`make dev-local` does not write credentials to disk. It maps the running local stack's database URL, API URL, and service-role key into the API process environment.

Use these checks when changing the upload pipeline:

```bash
make db-test          # Schema-level integration test
make db-test-upload   # Real local Storage and queued-lifecycle test
```

The browser always uploads through FastAPI. Supabase service credentials remain server-side.
