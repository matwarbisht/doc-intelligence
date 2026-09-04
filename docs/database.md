# Database Model

Stage 1 uses Supabase Postgres as the system of record, Supabase Storage for original files, Postgres full-text search for keyword retrieval, and pgvector for embeddings.

The versioned SQL files in `supabase/migrations/` are the schema source of truth. Domain models remain application-owned and do not import Supabase or database SDK types.

## Data flow

```text
documents
    └── document_versions
        ├── processing_jobs
        ├── document_elements
        ├── chunks
        │   ├── chunk_embeddings
        │   ├── entity_mentions
        │   ├── facts
        │   └── relationships
        └── extraction_runs
            ├── entities
            ├── facts
            └── relationships
```

`documents` is the stable identity for an uploaded file. Each processing attempt that produces canonical output gets an immutable `document_versions` record. Derived records point to that version, and facts, mentions, and relationships also retain their source chunk so answers can cite evidence.

## Tables

- `documents`: original-file metadata, storage location, content hash, and lifecycle status.
- `document_versions`: immutable parser/version boundary for reprocessing.
- `processing_jobs`: stage progress, attempts, timing, and failures.
- `document_elements`: canonical headings, paragraphs, lists, tables, images, and related structure.
- `chunks`: retrieval units with page and source-element provenance plus a generated full-text vector.
- `chunk_embeddings`: provider- and model-versioned pgvector values.
- `extraction_runs`: versioned model, prompt, and schema information for structured extraction.
- `entities` and `entity_mentions`: normalized entities and their evidence locations.
- `facts`: flexible subject-predicate-object facts with source chunks.
- `relationships`: entity relationships or entity-to-text relationships with source chunks.
- `queries`: minimal query history for MVP diagnostics and later evaluation.

## Embedding strategy

The MVP stores a dimensionless `vector` column and records the dimension on every row. This keeps the embedding provider replaceable while the model choice is still being evaluated. Queries must filter to one provider, model, and dimension before applying distance operations.

No approximate-nearest-neighbor index is created initially. Exact search is simpler and performs well for a small MVP corpus. Add an HNSW index after the embedding model is fixed and measurements show it is needed.

## Migrations

The first migration creates the public schema and enables pgvector. The second configures a private `documents` Storage bucket with a 50 MB limit for supported Stage 1 file types.

Apply migrations through the Supabase CLI or the project's hosted Supabase migration workflow. To verify an already-migrated database from the API test suite:

```bash
cd apps/api
TEST_DATABASE_URL=postgresql://... uv run pytest -m integration
```

The normal test suite skips that check when `TEST_DATABASE_URL` is absent. Row-level security is enabled on every public table without browser-facing policies, and the Storage bucket is private. During Stage 1, only the backend service role may access this data. Its credentials must never be exposed to the browser. User-scoped policies arrive with authentication and multi-tenancy.

## Local development

A Docker-compatible runtime must be running before using the local stack.

```bash
make db-start     # Start local Supabase and apply migrations/seeds
make db-status    # Show local service URLs and credentials
make db-reset     # Recreate the database from migrations and seed.sql
make db-test      # Run integration tests against local Postgres
make db-test-upload # Exercise local Storage and the processing pipeline
make db-verify    # Reset from scratch, then run all integration tests
make db-stop      # Stop local Supabase while retaining its data
```

The synthetic records in `supabase/seed.sql` are safe to commit and are recreated by `make db-reset`. Use the local database for daily development and automated integration checks. Reserve a separate hosted development project for deployment verification and provider-backed end-to-end testing; never point local reset commands at production.
