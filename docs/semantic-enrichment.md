# Semantic Enrichment and Indexing

Phase 5 turns canonical chunks into reusable semantic intelligence and searchable vectors while retaining evidence links to the source text.

## Pipeline

```text
canonical chunks
      ↓
Gemini structured extraction
      ↓
summary + document type + topics
entities + mentions + facts + relationships
      ↓
Gemini retrieval-document embeddings
      ↓
pgvector + full-text index
      ↓
ready
```

`DocumentPipelineService` composes the Phase 4 parser with Phase 5 enrichment. New uploads proceed through the whole pipeline when both Unstructured and Gemini are configured. The existing process endpoint can resume documents after configuration changes or retry eligible failed stages.

## Provider boundaries

`SemanticExtractor` and `EmbeddingProvider` are application-owned protocols. Gemini-specific request and response formats stop at their adapters.

Extraction uses structured JSON output validated against `SemanticExtraction`. The prompt requires every mention, fact, and relationship to cite an exact input chunk UUID. The persistence layer rejects unknown source identifiers before writing derived data.

Embeddings use `gemini-embedding-001` with the `RETRIEVAL_DOCUMENT` task type and 768 dimensions by default. Reduced vectors are normalized before storage. Each row records provider, model, model version, and dimension so future model changes remain explicit.

## Persistence and retries

Each extraction attempt creates a versioned `extraction_runs` record containing provider, model, prompt, and schema versions. Successful data is persisted transactionally with its entities, mentions, facts, and relationships. Facts and relationships point directly to their evidence chunk.

Processing jobs are atomically claimed and remain retryable up to `PROCESSING_MAX_ATTEMPTS`. Stale running jobs can be reclaimed. Extraction and embedding failures move the document into their corresponding failure state without exposing provider response bodies or credentials.

The indexing stage completes after Postgres has both the generated full-text vectors and chunk embeddings. The document then becomes `ready`.

## Document detail API

`GET /api/v1/documents/{document_id}` returns:

- file metadata and current lifecycle status;
- every processing stage and attempt count;
- summary, document type, and topics;
- entities, facts, and relationships;
- source chunk excerpts and page ranges; and
- chunk and embedding counts.

The frontend polls active documents and provides a detail page where extracted facts and relationships remain visibly connected to source excerpts.

## Configuration

```bash
GEMINI_API_KEY=replace-with-your-key
GEMINI_EXTRACTION_MODEL=gemini-3.6-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIMENSION=768
GEMINI_TIMEOUT_SECONDS=120
GEMINI_EMBEDDING_CONCURRENCY=5
```

Keep the API key only in `.env`; never expose it through Vite variables or commit it. Restart `make dev-local` after changing configuration. Documents already waiting in `extracting` can be resumed through `POST /api/v1/documents/{document_id}/process`.
