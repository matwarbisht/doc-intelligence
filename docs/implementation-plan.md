# Stage 1 Implementation Plan

The Stage 1 MVP is delivered as a sequence of small, verifiable milestones. Each phase should leave the repository runnable and keep provider-specific code behind application-owned boundaries.

## Phase 0 — Repository foundation (complete)

- Establish the pnpm monorepo and FastAPI application.
- Add shared commands, CI, environment examples, and architecture documentation.
- Verify the frontend and backend run together locally.

## Phase 0.5 — Design system (complete)

- Define design tokens, semantic themes, and foundational components.
- Add the style-guide route for visual verification.

## Phase 1 — Domain and persistence foundation (complete)

- Define infrastructure-independent domain models.
- Create the Stage 1 relational schema, pgvector storage, full-text index, provenance links, and private document bucket.
- Add the repository boundary and Postgres adapter.
- Cover domain and migration contracts with automated tests.

## Phase 2 — Local platform and persistence validation

The goal is a reproducible local data environment before building product workflows.

- Install and pin the Supabase CLI as a repository development dependency.
- Use a Docker-compatible runtime to run local Postgres, pgvector, Storage, API, and Studio services.
- Add commands for starting, stopping, inspecting, resetting, and testing the local stack.
- Apply every migration from scratch with `supabase db reset`.
- Add deterministic, synthetic seed records for development.
- Configure FastAPI to connect through the local `DATABASE_URL`.
- Run the database integration test against the migrated local database.
- Document the daily workflow and the boundary between local and hosted environments.
- Confirm the repository can recreate its database from only committed migrations and seeds.

Phase 2 is complete when a fresh checkout can start Supabase, rebuild the schema, load safe seed data, and pass the integration test without using the hosted project.

## Phase 3 — Upload and document lifecycle

- Build the upload and document-list API endpoints.
- Store originals in the private document bucket.
- Persist document metadata and processing state.
- Add the upload, document list, and initial status UI.

## Phase 4 — Parsing and canonicalization

- Add the parser provider contract and Unstructured adapter.
- Normalize parser output into canonical elements.
- Create chunks with page and element provenance.
- Make processing idempotent and retry-safe.

## Phase 5 — Semantic enrichment and indexing

- Add Gemini extraction and embedding adapters.
- Persist summaries, topics, entities, facts, relationships, and embeddings.
- Expose processing progress and document-detail data.

## Phase 6 — Retrieval and cited answers

- Implement keyword, semantic, structured, and hybrid retrieval.
- Generate corpus answers grounded in retrieved chunks.
- Return and display citations that resolve to source evidence.

## Phase 7 — MVP hardening and deployment

- Add the safe example corpus and end-to-end tests.
- Add operational logging, failure recovery, cost limits, and deployment configuration.
- Validate the complete upload-to-cited-answer user flow.
