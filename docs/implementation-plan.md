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

## Phase 2 — Local platform and persistence validation (complete)

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

## Phase 3 — Upload and document lifecycle (complete)

- Build the upload and document-list API endpoints.
- Store originals in the private document bucket.
- Persist document metadata and processing state.
- Add the upload, document list, and initial status UI.

## Phase 4 — Parsing and canonicalization (complete)

- Add the parser provider contract and Unstructured adapter.
- Normalize parser output into canonical elements.
- Create chunks with page and element provenance.
- Make processing idempotent and retry-safe.

## Phase 5 — Semantic enrichment and indexing (complete)

- Add Gemini extraction and embedding adapters.
- Persist summaries, topics, entities, facts, relationships, and embeddings.
- Expose processing progress and document-detail data.

## Phase 6 — Retrieval and cited answers (complete)

- Implement keyword, semantic, structured, and hybrid retrieval.
- Generate corpus answers grounded in retrieved chunks.
- Return and display citations that resolve to source evidence.

## Phase 7 — MVP hardening and deployment (complete)

- Add a safe, explicitly synthetic example corpus and deterministic end-to-end coverage.
- Add request-correlated operational logs without recording document content or credentials.
- Reject extraction inputs that exceed configurable chunk and character budgets.
- Let users retry a failed processing pipeline from the document detail screen.
- Package the frontend and API as provider-neutral, non-root containers.
- Document production configuration and the current background-task runtime constraint.
- Validate the complete upload-to-cited-answer user flow locally and with the optional
  provider-backed `make live-e2e` smoke test.

## Phase 8 — Enhancement: scoped question answering (complete)

- Keep global corpus questioning as the default `/ask` experience.
- Let users constrain an answer to one ready document with a visible scope selector.
- Provide both an “All documents” selector option and an explicit clear-scope action.
- Persist the scope in the URL as `/ask?document=<document-id>` so it survives refreshes
  and can be linked directly.
- Add an “Ask about this document” entry point to ready document-detail pages.
- Enforce the optional document scope in keyword, semantic, and structured retrieval
  before fusion and answer generation.
- Retain the selected document ID in query history for diagnostics and evaluation.

## Phase 9 — Enhancement: bulk document ingestion (complete)

- Replace the native single-file input with a styled, accessible drag-and-drop surface.
- Accept multiple supported documents through drag-and-drop or the file picker.
- Show a persistent per-file queue with pending, uploading, uploaded, duplicate, and
  failed states.
- Preserve partial success and let users retry failures or clear completed items.
- Reuse the existing single-document API with three concurrent browser uploads.
- Bound complete backend processing pipelines with configurable shared concurrency so
  bulk ingestion cannot fan out unlimited provider work.
- Serialize Unstructured jobs independently, retry transient provider throttling, and
  keep document-detail polling active while an accepted retry waits for capacity.

## Phase 10 — Authentication and abuse prevention (in progress)

The detailed design and rollout checklist live in the
[authentication and abuse-prevention plan](./authentication-and-abuse-prevention-plan.md).

### Phase 10A — Identity and corpus ownership (complete)

- Add public Supabase email/password sign-up, sign-in, persisted sessions, and sign-out.
- Protect document, retry, and question-answering routes while keeping health endpoints public.
- Validate bearer sessions authoritatively through Supabase Auth and block suspended profiles.
- Attach refreshed access tokens in the shared API client with one bounded `401` retry.
- Add document and query ownership, owner-prefixed object paths, and per-owner deduplication.
- Scope every document lookup and retrieval branch to the authenticated user and return an
  existence-safe `404` for another user's document.
- Add cross-user isolation tests and verify the flow against the real local Supabase Auth stack.

### Phase 10B — Ownership rollout and contract (complete)

- Add a dry-run-capable command to assign pre-authentication data to an explicit operator UUID.
- Verify there are no orphaned documents, queries, or mismatched document-scoped queries.
- Enforce non-null ownership only after the backfill has been run in each existing environment.

### Phase 10C — Demo-ready abuse controls (complete)

- Add server configuration switches for signup, uploads, processing, retries, and questions,
  plus a public capability response for clear disabled-state UI.
- Add atomic Postgres fixed-window counters for per-user/IP request limits, daily upload,
  byte, retry, and ask quotas, retry cooldowns, global intake budgets, and stored-document caps.
- Compensate upload acceptance reservations on invalid, duplicate, or failed uploads while
  retaining request-rate accounting.
- Return typed `429`/`503` errors and `Retry-After`, hash direct peer IPs with a server secret,
  and retain only sanitized usage events.
- Retain an optional, inactive threshold-event boundary for future alert delivery and provide
  dry-run-first cleanup tooling plus the operator kill-switch runbook.
- Keep public signup available by default while documenting the separate authoritative
  Supabase registration shutdown.
- Attribute background and query provider attempts to the owning user.
- Reserve operation-specific Unstructured and Gemini budgets immediately before every actual
  provider attempt, including adapter retries.
- Record sanitized provider outcomes and open bounded per-operation circuits after clustered
  `429` or retryable `5xx` responses.
- Verify feature shutdown, hard budgets, adapter retry accounting, circuit behavior, and
  cross-user isolation with deterministic tests that make no real provider calls.

The following are deliberately deferred until production readiness: server/external alert
delivery, provider-dashboard alerts, production TLS/CORS validation, quota-exhaustion
rehearsal, and provider-key rotation rehearsal. They are not required for the current
controlled demo, and no claim is made that unattended public operation is ready.
