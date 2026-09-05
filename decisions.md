# Engineering Decisions

This is a running record of consequential product and engineering calls made while building Document Intelligence. It records what we chose, the credible alternatives, why the choice fit the project at the time, and what we intentionally left out.

New decisions should be appended when a choice meaningfully affects architecture, product scope, operations, cost, security, or future implementation. If a decision changes, keep the original entry and add a superseding one so the history remains honest.

## D001 — Ship Stage 1 as one complete vertical slice

**The decision** — Build Stage 1 around one end-to-end path: upload a document, preserve it, parse it, canonicalize it, enrich it, index it, and answer questions with source citations.

**The alternatives** — Build horizontal platform layers for all three planned stages; begin with authentication and account infrastructure; or build a parsing-only proof of concept.

**The reasoning** — The vertical slice proves the risky parts of the product together: heterogeneous ingestion, provider integration, provenance, retrieval, and grounded answers. A parsing-only demo would not validate the product, while building later-stage platform features first would delay feedback on the core value.

**What we deliberately cut** — Stage 2 and Stage 3 capabilities, authentication, billing, multi-tenancy, enterprise permissions, and large-scale operations. They do not help validate the first upload-to-answer workflow.

## D002 — Use a small monorepo

**The decision** — Keep the independently deployable frontend and backend in one repository under `apps/`, with reusable internal code under `packages/`. Use a pnpm workspace for JavaScript packages without adding a monorepo framework.

**The alternatives** — Separate frontend and backend repositories; a single undifferentiated application directory; or a heavier workspace orchestrator such as Nx or Turborepo.

**The reasoning** — The web app, API contract, migrations, and local tooling change together during the MVP. One repository makes those changes atomic and keeps setup simple. `apps/` preserves deployment boundaries, while `packages/` gives shared code an explicit home. At this size, Make and pnpm provide enough orchestration without another configuration layer.

**What we deliberately cut** — Independent repository release cycles, remote build caching, affected-project graphs, and generalized shared packages. We will add a package only when a real reuse or ownership boundary exists.

## D003 — Use React, TypeScript, and Vite instead of Next.js

**The decision** — Build the frontend as a React and TypeScript single-page application bundled by Vite, with React Router for client-side routes and TanStack Query for server state.

**The alternatives** — Next.js, another React meta-framework, or server-rendered templates from FastAPI.

**The reasoning** — The product is an authenticated-style application UI whose data and processing live behind a separate FastAPI service. Stage 1 does not need SEO, server components, or framework-owned backend routes. Vite gives a small, fast frontend boundary and avoids running a second application server solely for rendering.

**What we deliberately cut** — Server-side rendering, static site generation, React Server Components, and framework API routes. We can revisit rendering strategy if public, indexable pages become a product requirement.

## D004 — Use FastAPI and Python for the backend

**The decision** — Implement the HTTP API and processing orchestration in Python with FastAPI, Pydantic, and uv.

**The alternatives** — A Node.js/TypeScript backend shared with the frontend, Django, or a serverless collection of functions.

**The reasoning** — Python fits the document-processing and AI integration ecosystem, while FastAPI gives validated contracts, async I/O, and OpenAPI without a large framework footprint. Keeping the API independently deployable prevents browser concerns from leaking into processing code. uv supplies reproducible Python dependency management alongside pnpm on the frontend.

**What we deliberately cut** — A shared frontend/backend runtime, a full Django admin and ORM stack, and function-per-endpoint deployment. Those benefits do not outweigh the added coupling or operational shape for the MVP.

## D005 — Keep application-owned boundaries around infrastructure

**The decision** — Routes call services; services coordinate domain models; provider protocols isolate Storage, Unstructured, Gemini, and embeddings; repository protocols isolate persistence. Domain models do not import provider or database SDK types.

**The alternatives** — Call Supabase and AI providers directly from routes, persist provider response objects, or build a more elaborate clean-architecture framework before implementing features.

**The reasoning** — Parsing, model, embedding, and storage providers are expected to change. Narrow application-owned interfaces contain that volatility and make deterministic testing possible. The boundaries are introduced only when backed by real behavior, which avoids an abstraction-heavy skeleton.

**What we deliberately cut** — A plugin system, dependency-injection framework, generic base repositories, and empty interfaces for hypothetical providers.

## D006 — Maintain a dedicated typed API-client package

**The decision** — Put browser-facing request functions and TypeScript response types in `packages/api-client` instead of scattering `fetch` calls through React components.

**The alternatives** — Component-local requests, importing generated database types into the browser, or introducing OpenAPI generation immediately.

**The reasoning** — A client package centralizes URLs, errors, request shapes, and the future authentication header boundary. It also makes backend contract drift fail during frontend type checking. The current contract is still small enough that handwritten types are easier to inspect than a generator pipeline.

**What we deliberately cut** — Automatic OpenAPI client generation for now. We will introduce it when the endpoint surface is large enough that maintaining handwritten types becomes the bigger risk.

## D007 — Build a lightweight token-based design system first

**The decision** — Add a Phase 0.5 design system using Inter, Radix color scales, CSS custom properties, semantic tokens, SCSS Modules, and native React components. Support light, dark, and system themes and keep `/style-guide` as the visual playground.

**The alternatives** — Tailwind CSS, shadcn/ui, CSS-in-JS, raw per-screen CSS, or a full component library.

**The reasoning** — Tokens establish a consistent visual language before product screens multiply. Radix supplies coherent primitives, semantic aliases protect components from palette changes, and SCSS Modules keep styles local without runtime styling overhead. Native Button, Input, and Card elements are sufficient and accessible for the first component set.

**What we deliberately cut** — Tailwind, shadcn-generated components, styled-components, and Base UI. Base UI remains an option only when a complex accessible primitive such as a dialog, select, popover, or tooltip is actually needed.

## D008 — Use Supabase Postgres as the system of record

**The decision** — Store application data in Supabase Postgres, original files in a private Supabase Storage bucket, keyword-search vectors in Postgres, and semantic vectors through pgvector.

**The alternatives** — Separate managed services for relational data, object storage, and vector search; a document database; or storing files directly in Postgres.

**The reasoning** — Stage 1 query patterns are relational: documents have versions, jobs, elements, chunks, extraction runs, facts, and evidence links. Postgres models these relationships and transactions well. Supabase provides Postgres, Storage, and a reproducible local stack, while pgvector avoids operating and synchronizing a second search datastore during the MVP.

**What we deliberately cut** — A dedicated vector database, Elasticsearch/OpenSearch, a separate object-storage vendor, and multi-region data infrastructure. Corpus scale and retrieval measurements should justify those systems before we add them.

## D009 — Use versioned SQL migrations and direct asyncpg persistence

**The decision** — Treat SQL migrations as the database source of truth and implement persistence with explicit SQL through asyncpg behind repository interfaces.

**The alternatives** — SQLAlchemy plus Alembic, Supabase-generated browser/database clients throughout the backend, or dashboard-only schema changes.

**The reasoning** — The schema relies on transactions, pgvector, generated search vectors, indexes, constraints, RLS, and evidence relationships. Explicit SQL makes these behaviors reviewable and keeps migration output reproducible. asyncpg gives a small asynchronous runtime layer without making domain models ORM entities.

**What we deliberately cut** — ORM identity maps, generic CRUD repositories, and manual production schema edits. If query volume and model repetition make direct SQL costly, an ORM can be reconsidered without changing the service contracts.

## D010 — Make local infrastructure reproducible and disposable

**The decision** — Pin the Supabase CLI in the repository, run the local Supabase stack through Docker-compatible tooling, use deterministic seed data, and expose common workflows through Make and repository scripts.

**The alternatives** — Develop only against a shared hosted database; require globally installed tool versions; or let every developer assemble commands and credentials manually.

**The reasoning** — Database and Storage behavior are central to the product and need integration testing before deployment exists. A resettable local stack makes migrations testable from a clean state and avoids shared-environment collisions. `make dev-local` injects local credentials into processes without writing them into tracked files.

**What we deliberately cut** — Production-like cloud environments for every branch and committed local credentials. Hosted-environment verification is deferred until deployment work.

## D011 — Preserve originals and create an application-owned canonical model

**The decision** — Keep every original in private object storage, then normalize parser output into versioned canonical elements and retrieval chunks with page and source-element provenance.

**The alternatives** — Store only extracted text, persist Unstructured's response as the domain model, overwrite derived data in place, or force documents into domain-specific schemas during ingestion.

**The reasoning** — The product must support unknown document domains and future reprocessing. Originals are the recovery point; canonical elements retain useful structure without coupling downstream logic to a parser; immutable document versions preserve which parser output produced each derived record. This implements the principle “understand first, impose schema later.”

**What we deliberately cut** — Lossy text-only ingestion, a predefined invoice/contract/report schema, and a full visual layout graph. Specialized schemas can be derived later when repeated use cases justify them.

## D012 — Limit the first upload surface and deduplicate by content

**The decision** — Accept PDF, DOCX, Markdown, and plain text up to 50 MB, calculate a SHA-256 content hash, and return the existing document when identical bytes are uploaded again.

**The alternatives** — Accept every format listed in the long-term PRD immediately, deduplicate by filename, permit duplicate copies, or rely only on Storage limits.

**The reasoning** — These formats exercise structured and unstructured ingestion without opening every parser edge case. Enforcing the limit in both the API and bucket fails early and consistently. Content hashing identifies the same file despite renaming and avoids paying repeatedly for parsing and model calls.

**What we deliberately cut** — Spreadsheets, presentations, email, HTML, images, OCR-specific flows, resumable uploads, and user-controlled duplicate versions. They remain valid future ingestion work but are not needed for the first vertical slice.

## D013 — Keep documents private and route browser access through FastAPI

**The decision** — Use a private Storage bucket, enable RLS without browser-facing policies, keep the Supabase service role on the backend, and send browser uploads through FastAPI.

**The alternatives** — Public objects, direct browser uploads using the service role, or implementing user-scoped RLS policies before authentication exists.

**The reasoning** — Uploaded documents may be sensitive. The API must enforce file rules, deduplication, persistence, and cleanup as one application workflow. With no user identity model yet, permissive browser policies would create a false security boundary; backend-only access is the smallest safe Stage 1 posture.

**What we deliberately cut** — End-user authentication, signed direct-upload URLs, tenant-scoped policies, sharing, and fine-grained permissions. These must arrive together rather than as partial security features.

## D014 — Model processing as durable, retryable stages

**The decision** — Represent `queued`, `parsing`, `extracting`, `embedding`, and `indexing` as durable jobs with explicit document statuses, bounded attempts, atomic claims, failure details, and stale-running recovery.

**The alternatives** — A single boolean such as `processed`, an in-memory progress map, or introducing a production queue and workers immediately.

**The reasoning** — Provider calls fail independently and can outlive an HTTP request. Persisted stages make progress inspectable and let processing resume without repeating successful work. Atomic claims and idempotent replacement protect against duplicate workers. The HTTP contract can remain stable when the lightweight executor is later replaced.

**What we deliberately cut** — A distributed queue, dedicated worker service, scheduling, priorities, dead-letter queues, and exactly-once delivery. Stage 1 currently starts work with FastAPI background tasks and uses the database as the durable state boundary.

## D015 — Use Unstructured behind a parser adapter

**The decision** — Use Unstructured's on-demand Jobs API with the `hi_res_partition` template, then map its output into application-owned canonical elements.

**The alternatives** — Build and maintain per-format parsing with libraries such as PDF and DOCX parsers, use synchronous long-running requests, or persist Unstructured-specific objects throughout the application.

**The reasoning** — Layout-aware parsing across heterogeneous formats is a large problem outside the product's differentiator. The Jobs API supports long-running work, while the adapter lets us replace the provider or add local parsing later. Canonicalization prevents provider fields and identifiers from becoming the permanent data contract.

**What we deliberately cut** — Custom OCR/layout models, per-format parsing pipelines, parser-provider fallback, and a provider-agnostic job scheduler.

## D016 — Chunk by document structure, not blind fixed windows

**The decision** — Start chunks at headings, keep related paragraphs and list items together while they fit, isolate tables, split oversized elements at word boundaries, and retain source element IDs and page ranges.

**The alternatives** — Fixed character/token windows with overlap, one chunk per parser element, or LLM-generated chunks.

**The reasoning** — Retrieval needs units that are bounded but still semantically coherent. Structural boundaries improve context quality and citations, while deterministic chunking is cheap, repeatable, and testable. Provenance lets a retrieved chunk resolve back to its source structure.

**What we deliberately cut** — Tokenizer-specific sizing, semantic breakpoint models, context-enriched chunk rewriting, and chunk-quality optimization. Those should be driven by Phase 6 retrieval evaluation.

## D017 — Extract generic semantic records with evidence

**The decision** — Use Gemini structured output to derive a concise summary, document type, topics, entities and mentions, subject-predicate-object facts, and relationships. Require facts, mentions, and relationships to cite an exact input chunk UUID, and reject unknown citations before persistence.

**The alternatives** — Store only an LLM summary, create a rigid domain schema, accept free-form JSON, or extract claims without direct evidence links.

**The reasoning** — Generic records make arbitrary documents queryable without pretending every domain shares one schema. A validated response schema reduces parsing ambiguity, and chunk-level evidence is essential for debugging and grounded answers. Extraction runs record model, prompt, and schema versions so later changes are attributable.

**What we deliberately cut** — Domain-specific ontologies, entity resolution across documents, human review workflows, confidence calibration, and automatic schema induction.

## D018 — Use Gemini embeddings in Postgres with an explicit index contract

**The decision** — Generate `RETRIEVAL_DOCUMENT` embeddings with `gemini-embedding-001`, reduce them to 768 dimensions, normalize them, store provider/model/dimension metadata, and use a filtered HNSW cosine index.

**The alternatives** — Full-size vectors, OpenAI or local embedding models, a fixed `vector(768)` column, brute-force distance scans, or a dedicated vector database.

**The reasoning** — A 768-dimensional vector is a pragmatic storage/search-quality tradeoff for the MVP. Normalization makes cosine comparisons predictable. A dimensionless column keeps future providers possible, while the filtered index makes the active provider/dimension combination fast and explicit instead of mixing incompatible vectors.

**What we deliberately cut** — Multiple simultaneous embedding models, automated re-embedding, benchmark-driven dimension selection, hybrid-ranking calibration, and external vector infrastructure. Phase 6 retrieval tests should determine whether any of these are necessary.

## D019 — Pin a supported Gemini extraction model

**The decision** — Default semantic extraction to the stable `gemini-3.6-flash` model while keeping the model configurable through `GEMINI_EXTRACTION_MODEL`.

**The alternatives** — Continue using `gemini-2.5-flash`, use a moving `latest` alias, or immediately migrate the integration to Gemini's newer Interactions API.

**The reasoning** — `gemini-2.5-flash` returned HTTP 404 for new users during the first real end-to-end test, and Google's API directed new users to `gemini-3.6-flash`. Pinning an explicit stable model makes local and CI behavior more reproducible than a moving alias. Configuration still allows a deliberate model upgrade without code changes.

**What we deliberately cut** — Automatic model fallback and an Interactions API migration. Both add behavior and testing surface that are unnecessary to restore the Stage 1 extraction path.

## D020 — Sanitize provider failures but persist actionable stage errors

**The decision** — Convert provider failures into bounded application errors, persist the failed stage and safe message, and never expose provider response bodies, API keys, storage paths, or service credentials.

**The alternatives** — Return raw provider errors to the browser, log full responses for convenience, or hide every failure behind a generic document status.

**The reasoning** — Operators and users need to know which stage failed and whether it can be retried, but provider responses may contain sensitive or unstable details. Stage-specific errors preserve operational value while keeping external payloads behind the adapter boundary.

**What we deliberately cut** — Full observability, structured log aggregation, trace correlation, alerting, and user-facing diagnostic remediation. Those belong in MVP hardening.

## D021 — Use CI as a quality gate, not a deployment pipeline

**The decision** — Run formatting, linting, static type checks, unit tests, and the frontend production build on pushes to `main` and pull requests.

**The alternatives** — No CI until deployment; deploy on every push; or run provider-backed and Docker integration tests on every commit.

**The reasoning** — Cross-language changes can break formatting, contracts, types, and builds even before a deployment target exists. A validation-only workflow catches those regressions cheaply and makes the main branch reproducible without implying that the product is production-ready.

**What we deliberately cut** — Deployment jobs, cloud credentials, preview environments, browser end-to-end tests, and paid provider calls in CI. These will be added when Phase 7 defines environments and operational policy.

## D022 — Use deterministic hybrid retrieval before adding an LLM planner

**The decision** — Run keyword, semantic, and extracted-fact/entity retrieval concurrently for every Stage 1 question, then combine their ranked results with weighted reciprocal-rank fusion. Favor semantic results slightly, followed by structured and keyword matches.

**The alternatives** — Use semantic search alone; compare and add raw text-rank and cosine scores directly; or call an LLM first to classify every question and select one retriever.

**The reasoning** — The corpus is small enough to run all three retrievers, and each signal covers a real failure mode of the others. Reciprocal-rank fusion combines unlike score scales without brittle normalization. Always-on hybrid retrieval avoids the latency, cost, and new classification errors of a planner call while we still lack an evaluation set that could prove routing is better.

**What we deliberately cut** — Learned ranking, query rewriting, per-question route selection, configurable user filters, reranking models, and calibrated relevance thresholds. Phase 7 evaluation should provide evidence before tuning or replacing the deterministic baseline.

## D023 — Generate answers only from bounded, validated evidence

**The decision** — Give each fused chunk a stable source number, require Gemini to answer from those chunks with inline `[n]` markers and structured source-number/chunk-ID citations, reject mismatched citations, and return only cited sources. Do not call the answer model when retrieval returns no evidence.

**The alternatives** — Let the model answer from general knowledge, return retrieved chunks without an answer, trust free-form citations, or expose every retrieved candidate as if it supported the answer.

**The reasoning** — The product promise is auditable document intelligence, not an unconstrained chatbot. Validating both the ordinal and UUID prevents the model from citing nonexistent evidence. Returning only used sources makes the provenance contract honest, while the deterministic no-evidence response avoids cost and hallucination when grounding is impossible.

**What we deliberately cut** — Streaming answers, token-level citation spans, citation-entailment scoring, multi-turn chat memory, and automatic follow-up questions. Those require additional UX and evaluation work beyond the first cross-document answer flow.

## D024 — Treat retrieved document text as untrusted model input

**The decision** — Put the answer-grounding rules in a Gemini system instruction and explicitly tell the model that retrieved chunks are evidence, not instructions, and that commands embedded in documents must be ignored. Continue validating citations after generation.

**The alternatives** — Concatenate the question and retrieved text into one unconstrained prompt; attempt to sanitize natural-language documents; or postpone prompt-injection handling until authentication work.

**The reasoning** — Documents are user-controlled and can contain text designed to redirect the model. Separating control instructions from evidence and stating the trust boundary is a low-cost defense that fits the existing provider adapter. Citation validation independently limits fabricated provenance even if model behavior is imperfect.

**What we deliberately cut** — A full RAG-security policy engine, content classification, adversarial-model evaluation, and per-tenant retrieval authorization. System prompting is defense in depth, not a complete security boundary; stronger controls belong in Phase 7 and the later authentication phase.

## D025 — Keep Phase 7 deployment provider-neutral

**The decision** — Package the Vite application as an unprivileged Nginx container and FastAPI as a non-root Python container, with public URLs and secrets supplied through explicit environment contracts. Do not select a hosting vendor in the repository yet.

**The alternatives** — Commit Vercel plus Render/Fly.io configuration now; combine the frontend and API into one image; or defer every deployment artifact until a host is chosen.

**The reasoning** — The web and API already have independent runtime needs, and ordinary OCI images run on the credible hosting options without coupling architecture to one vendor. A static web image also preserves client-side routing and cache policy. The separation makes the compiled public API URL explicit and keeps service-role and provider credentials out of the browser.

**What we deliberately cut** — Provider manifests, DNS, TLS, autoscaling, preview environments, and continuous deployment. Those choices depend on the eventual host, budget, and operational owner.

## D026 — Reject extraction work above explicit input budgets

**The decision** — Count canonical chunks and characters before a Gemini extraction call and fail the extraction stage when either configurable maximum is exceeded.

**The alternatives** — Send any accepted upload to the model; silently truncate the document; estimate and enforce a monetary budget after calls; or split large documents into multiple model calls immediately.

**The reasoning** — The upload-size limit does not predict parsed text volume or provider cost. A deterministic preflight bound prevents accidental high-cost requests and produces an actionable, retryable stage failure. Failing visibly preserves correctness better than silently extracting from only part of a document.

**What we deliberately cut** — Token-level estimation, automatic map-reduce extraction, per-user budgets, invoices, and adaptive truncation. They require product policy and quality evaluation beyond this single-user MVP.

## D027 — Use structured stdout logs and request IDs before an observability vendor

**The decision** — Emit configurable console or JSON logs to stdout, propagate or create an `x-request-id`, and log HTTP timing, durable processing transitions, and retrieval counts using an allowlist of fields.

**The alternatives** — Integrate a hosted logging/APM SDK; write logs to local files; include full provider payloads and document text; or rely only on persisted job status.

**The reasoning** — Container platforms capture stdout, and JSON plus a request ID is enough to trace an upload or query across the current single API service. Allowlisting context keeps logs useful without leaking document content, credentials, or arbitrary provider responses. It also leaves the aggregation vendor replaceable.

**What we deliberately cut** — Distributed traces, metrics, dashboards, alerts, sampling, and an observability vendor. Add them when a selected deployment and real service-level objectives define what must be measured.

## D028 — Separate deterministic product tests from paid live smoke tests

**The decision** — Exercise upload, parsing, enrichment, retrieval, answer generation, citations, and persistence in one database integration test with deterministic provider doubles. Keep a separate opt-in `make live-e2e` command for the same user path through real Unstructured and Gemini services using synthetic data.

**The alternatives** — Call paid providers from CI; test every layer only in isolation; or use recorded provider responses as the sole end-to-end check.

**The reasoning** — Deterministic doubles make the complete application orchestration fast and repeatable without network flakiness, quota, or secrets in CI. The live smoke catches provider-contract and credential drift that doubles cannot, while making its cost and local data mutation explicit.

**What we deliberately cut** — Paid-provider CI, browser automation, a large retrieval benchmark, and scheduled canary traffic. The small evaluation manifest is a seed for later measurement, not a claim of retrieval quality.

## D029 — Expose manual recovery before adding automatic retry infrastructure

**The decision** — Show a retry action on failed document details and reuse the existing idempotent processing endpoint and durable job state.

**The alternatives** — Require database intervention; automatically retry indefinitely; add a scheduler and dead-letter queue; or create separate retry endpoints for every processing stage.

**The reasoning** — The existing pipeline already knows which durable stages succeeded and atomically claims retryable work. A user-triggered retry supplies immediate recovery without hiding repeated provider or configuration failures and without introducing another runtime service before deployment needs are known.

**What we deliberately cut** — Backoff schedules, automatic retry policy by error class, dead-letter administration, and bulk retries. Those become important when processing no longer has an attentive MVP operator.

## D030 — Model document-level questions as an optional retrieval scope

**The decision** — Keep one `/ask` experience and one query endpoint, with an optional document UUID that is applied to keyword, semantic, and structured retrieval before fusion. Store the selection in the `document` URL query parameter and persist it with query history.

**The alternatives** — Build a separate document-chat screen and endpoint; filter globally retrieved results in the browser; inject the filename into the natural-language question; or maintain the selection only in React state.

**The reasoning** — Global and document-level questions share retrieval, grounding, citations, and presentation; only the eligible evidence set changes. A backend constraint guarantees that unrelated evidence cannot leak into a scoped answer. A query parameter makes the state refreshable, bookmarkable, and suitable for the document-detail entry point without creating duplicate routes or interfaces.

**What we deliberately cut** — Multi-document manual selection, saved scopes, folders, conversational threads, and document comparison mode. Those require additional selection and history semantics; the MVP enhancement needs only “all documents” or exactly one ready document.

## D031 — Retry only transient Gemini failures at the provider boundary

**The decision** — Retry Gemini network errors and HTTP 429, 500, 502, 503, and 504 responses with configurable bounded attempts and exponential delay. Apply the policy consistently to answer generation, extraction, and embeddings; fail non-transient HTTP errors immediately.

**The alternatives** — Surface every provider failure immediately; retry all errors indiscriminately; retry the whole query service including retrieval and persistence; or add a general-purpose resilience library.

**The reasoning** — The first scoped-query test completed retrieval but Gemini briefly returned 503, while a later request succeeded. Retrying at the adapter boundary repeats only the failed external call, avoids duplicating query records or database work, and contains provider-specific policy. Bounded attempts prevent an outage or quota condition from hanging requests indefinitely.

**What we deliberately cut** — Circuit breakers, jitter, `Retry-After` parsing, cross-request retry queues, and provider fallback. Those are useful at higher traffic but add operational policy that the local MVP does not yet need.

## D032 — Orchestrate bulk ingestion over the single-document API

**The decision** — Add a drag-and-drop, multi-file queue in the browser while continuing to upload each file through `POST /documents`. Limit browser uploads to three at a time and wrap the shared backend processing pipeline in a configurable concurrency semaphore.

**The alternatives** — Add one multipart bulk endpoint; accept an archive and unpack it on the server; start every selected upload and processing job simultaneously; or wait for a distributed queue before supporting batches.

**The reasoning** — The existing endpoint already owns type and size validation, content-hash deduplication, private storage, cleanup, and durable job creation. One request per file preserves those guarantees and makes partial success natural: an invalid document does not roll back valid ones. Browser concurrency protects upload bandwidth, while the backend limit protects Unstructured and Gemini even when requests come from multiple tabs or users.

**What we deliberately cut** — Atomic batches, folder hierarchy, archive ingestion, pause/resume, byte-level upload progress, resumable uploads, and a dedicated worker queue. They add server-side batch identity or transport machinery that is unnecessary for the current document sizes and MVP runtime.

## D033 — Limit concurrency at the provider boundary and follow accepted retries

**The decision** — Keep up to three application pipelines in flight, but serialize complete Unstructured parsing jobs with a separate configurable semaphore. Retry transient Unstructured network, 429, and selected 5xx failures at the adapter boundary. After a user retries a failed document, keep polling its detail record until a new processing attempt reaches a terminal state.

**The alternatives** — Reduce every pipeline stage to one-at-a-time; make the browser upload files sequentially; treat provider throttling as a permanent parsing failure; continuously poll every document-detail page; or optimistically assume the first refresh after a retry will observe a running job.

**The reasoning** — Local job records showed that the bulk failures were all Unstructured HTTP 429 responses while one accepted job continued normally. Limiting only the constrained provider preserves overlap between parsing and Gemini enrichment without exceeding that active-job limit. A bounded adapter retry absorbs short throttling windows without repeating database claims. Retry-aware polling closes the race where the API accepts background work before the worker acquires capacity and changes the stored failed status.

**What we deliberately cut** — A durable external work queue, automatic recovery of already failed documents, provider-plan discovery, adaptive concurrency, bulk retry controls, and server-pushed status events. They are useful later, but explicit local limits and targeted polling solve the observed MVP failure without adding infrastructure.

## D034 — Treat the local frontend and API as one supervised process group

**The decision** — Check the fixed development ports before launching, place each server and its reload descendants in a separate process group, terminate those groups together, and stop the sibling application when either server exits.

**The alternatives** — Keep relying on direct child PIDs; automatically kill any process occupying ports 5173 or 8000; run the services in separate terminals; or introduce a container orchestrator for application development.

**The reasoning** — Uvicorn's reload process outlived the launcher long enough for a restart to fail with “address already in use”; after that old process exited, Vite remained available while no API was running. Process-group cleanup covers reload descendants, early port checks explain conflicts before a partial stack starts, and sibling supervision prevents a working UI shell from masking an API startup failure. Refusing to kill an unknown port owner avoids disrupting unrelated local work.

**What we deliberately cut** — Automatic port reassignment, automatic termination of unknown processes, Docker Compose for the application services, and a general-purpose process supervisor. Fixed URLs and a small shell launcher remain appropriate for this local MVP.

## D035 — Use Supabase Auth for public email/password accounts

**The decision** — Use Supabase Auth for public email/password signup and sessions, with an application-owned `profiles` row for active or suspended state. Keep signup enabled during the limited test and protect product routes in both the React router and FastAPI.

**The alternatives** — Build password storage and sessions in FastAPI; use a shared tester password; disable public signup and provision every tester manually; or start with magic links and OAuth.

**The reasoning** — Authentication is now a data-isolation boundary, not merely a launch gate. Supabase is already part of the stack and provides password hashing, session refresh, and future identity methods without putting credential handling in our application. A separate profile keeps product policy such as suspension independent from the identity provider record.

**What we deliberately cut** — Email confirmation, password recovery, magic links, OAuth, account linking, organizations, and an account-settings screen. The model keeps an immutable provider user UUID so those can be added without changing document ownership.

## D036 — Make ownership explicit at document and query boundaries

**The decision** — Store `documents.owner_id` and `queries.user_id`; derive ownership of versions, chunks, extraction records, and embeddings through their parent document. Scope every repository lookup and retrieval branch before returning or ranking data, prefix new storage objects by user, and deduplicate content only inside one user's corpus.

**The alternatives** — Add `user_id` to every derived table; infer ownership from storage paths; keep global deduplication; or rely on frontend filtering and database RLS alone.

**The reasoning** — The document is the aggregate root for all processed knowledge, so one authoritative owner avoids denormalized ownership becoming inconsistent. Backend filters remain the primary boundary because the API's privileged database connection is not protected by browser RLS. Per-owner hashes also avoid revealing that another user uploaded the same bytes.

**What we deliberately cut** — Shared documents, workspaces, memberships, ownership transfers, and direct browser database access. Existing pre-authentication rows remain nullable and invisible until an explicit backfill owner is selected; a later contract migration will make ownership non-null.

## D037 — Validate sessions through Supabase Auth before optimizing with JWKS

**The decision** — Validate each API bearer token through Supabase Auth's user endpoint behind an `AuthenticationProvider` interface. Distinguish rejected sessions (`401`), suspended accounts (`403`), missing resources (`404`), and identity-provider outages (`503`). Let the shared API client refresh once after a `401` and retry exactly once.

**The alternatives** — Decode tokens without signature validation; immediately implement local JWT/JWKS verification; trust browser session state; or retry unauthorized requests indefinitely.

**The reasoning** — Supabase's authoritative endpoint works for the local HS256 configuration as well as hosted projects and validates the complete provider session contract. The provider boundary preserves a future move to cached JWKS verification if the added network hop becomes material. One refresh retry handles ordinary expiry without loops or duplicated unbounded traffic.

**What we deliberately cut** — A distributed token cache, local JWKS caching, device/session administration, token revocation lists, and custom access claims. We need measured hosted latency and traffic before accepting their added security and invalidation complexity.

## D038 — Contract ownership only after an explicit transactional backfill

**The decision** — Keep the ownership expansion and database contract as separate migrations. Require an operator-selected Supabase user UUID, inspect legacy counts without writing by default, assign only null ownership in one locked transaction, and make the later migration abort unless every document and query is owned and every scoped query matches its document owner.

**The alternatives** — Hard-code the first user into a migration; delete legacy records; leave ownership nullable indefinitely; infer an owner from email or timestamps; or silently assign records while deploying the application.

**The reasoning** — A repository migration cannot know who legitimately owns a pre-authentication corpus. An explicit dry run makes that human decision visible, while table locks and post-write verification prevent concurrent inserts from creating a gap during assignment. The final non-null and composite foreign-key constraints then turn the application rule into a database invariant.

**What we deliberately cut** — Automatic storage-object moves, owner guessing, a general ownership-transfer interface, and multi-user distribution of the legacy corpus. The safe MVP operation assigns the known single-user corpus to one reviewed account; future sharing needs workspace semantics rather than another one-off backfill.
