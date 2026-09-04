# Repository Structure

Document Intelligence uses a small monorepo: deployable applications live in `apps/`, while reusable internal libraries live in `packages/`.

```text
doc-intelligence/
├── apps/
│   ├── web/                    # React frontend
│   └── api/                    # FastAPI backend
│
├── packages/
│   └── api-client/             # Shared TypeScript API client boundary
│
├── supabase/
│   ├── migrations/             # Database migrations
│   ├── seed.sql                # Synthetic local development data
│   └── config.toml             # Local Supabase configuration
│
├── docs/                       # Architecture and engineering documentation
├── examples/                   # Safe example document corpus
├── scripts/
│   ├── dev.sh                  # One-command local server launcher
│   ├── dev-local.sh            # Local Supabase-aware app launcher
│   ├── supabase.sh             # Project-pinned local Supabase launcher
│   ├── test-local-upload.sh     # Storage and lifecycle integration test
│   └── uv.sh                   # Portable uv command resolver
├── .github/workflows/          # Continuous integration
├── .env.example                # Environment-variable template
├── Makefile                    # Common development commands
├── package.json                # Root JavaScript workspace configuration
├── pnpm-lock.yaml              # Locked JavaScript dependencies
├── pnpm-workspace.yaml         # pnpm workspace membership
└── README.md                   # Project introduction and setup
```

## Applications

The `apps/` directory contains runnable and independently deployable products.

### `apps/web`

The browser application is built with React, TypeScript, and Vite.

```text
apps/web/
├── src/
│   ├── app/
│   │   ├── App.tsx             # Top-level routes and application shell
│   │   ├── App.test.tsx        # Application smoke test
│   │   └── providers.tsx       # Router, query client, and future providers
│   ├── components/             # Button, Input, and Card primitives
│   ├── pages/
│   │   ├── HomePage.tsx
│   │   ├── NotFoundPage.tsx
│   │   └── StyleGuide/         # Design-system playground
│   ├── styles/                 # Global styles and design tokens
│   ├── test/
│   │   └── setup.ts            # Shared Vitest setup
│   ├── theme/                  # Light, dark, and system theme utility
│   ├── main.tsx                # Browser entry point
├── eslint.config.js
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

The frontend is responsible for:

- rendering and browser routing;
- upload and document-inspection experiences;
- processing-progress presentation;
- corpus search and question-answering interfaces;
- server-state synchronization with TanStack Query; and
- calling the backend through the shared API client.

It must not contain provider credentials, database access, document-processing logic, or authorization enforcement.

### `apps/api`

The backend is built with FastAPI and managed with uv.

```text
apps/api/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   └── health.py       # Health endpoint
│   │   └── router.py           # API router composition
│   ├── core/
│   │   └── config.py           # Validated application settings
│   ├── db/
│   │   └── pool.py             # asyncpg pool and database codecs
│   ├── domain/
│   │   └── models.py           # Infrastructure-independent domain models
│   ├── providers/              # Storage, Unstructured, and Gemini adapters
│   ├── repositories/
│   │   ├── document_repository.py          # Persistence protocol
│   │   ├── postgres_document_repository.py # Document Postgres adapter
│   │   ├── processing_repository.py        # Processing persistence protocol
│   │   ├── postgres_processing_repository.py # Processing Postgres adapter
│   │   ├── enrichment_repository.py        # Enrichment persistence protocol
│   │   └── postgres_enrichment_repository.py # Enrichment Postgres adapter
│   ├── services/               # Upload, parsing, enrichment, and pipeline orchestration
│   ├── schemas/
│   │   ├── documents.py        # Document HTTP schemas
│   │   └── health.py           # Health HTTP schema
│   └── main.py                 # FastAPI application entry point
├── tests/
│   └── test_health.py
├── .python-version
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

The backend is responsible for:

- exposing and validating the HTTP API;
- orchestrating document ingestion and processing;
- communicating with Supabase, Unstructured, and Gemini;
- persisting documents, elements, chunks, entities, and facts;
- executing retrieval and RAG workflows; and
- enforcing security and application rules.

The current backend boundaries are:

```text
app/
├── domain/                     # Infrastructure-independent models
├── services/                   # Use-case orchestration
├── providers/                  # Storage, parser, and future AI adapters
└── repositories/               # Persistence boundaries and adapters
```

New boundaries should still be introduced only when they contain real functionality rather than as empty architecture.

## Internal packages

The `packages/` directory contains reusable code consumed by one or more applications. Packages are not deployed independently.

The distinction is:

```text
apps/       runnable and deployable products
packages/   reusable internal libraries
```

Potential future packages include a shared UI system or common linting configuration. A new package should only be introduced when it creates a useful ownership or reuse boundary; application-specific code should remain in its application.

### `packages/api-client`

The API client is the frontend's typed gateway to FastAPI.

```text
packages/api-client/
├── src/
│   └── index.ts
├── package.json
└── tsconfig.json
```

Its intended data flow is:

```text
FastAPI Pydantic schemas
          ↓
FastAPI OpenAPI document
          ↓
generated TypeScript types and request functions
          ↓
packages/api-client
          ↓
React features and TanStack Query hooks
```

This keeps endpoint URLs, request and response types, error handling, and later authentication headers out of individual React components. It also lets backend contract changes surface as frontend compilation errors.

The package currently contains the typed upload, document-list, document-detail, and processing request functions. A later phase can replace the handwritten types with OpenAPI generation as the contract surface grows.

The API client must not contain backend business logic, database models, provider SDKs, or UI components.

## Database and storage configuration

### `supabase/`

This directory owns local Supabase configuration and version-controlled SQL migrations.

Phase 1 adds migrations for documents, document versions, processing jobs, canonical elements, chunks, extraction runs, entities, mentions, facts, relationships, queries, and vector support. See [Database Model](database.md).

Large original document files live in Supabase Storage rather than Postgres. Canonical elements and provenance-aware chunks produced by Phase 4 live in Postgres. Phase 5 adds versioned Gemini extraction results, evidence-linked semantic records, and provider/model-specific chunk embeddings. Phase 6 adds hybrid corpus retrieval, grounded answer generation, validated citations, and query history.

### `examples/`

This directory will contain a small, safe corpus for development and demonstrations. Only public or synthetic documents belong here; customer files, credentials, and personally identifiable information must not be committed.

## Root configuration

### `package.json` and `pnpm-workspace.yaml`

The root package file defines commands that operate across the JavaScript workspace. The workspace file registers `apps/web` and every directory under `packages/` as pnpm workspace members.

This allows the frontend to consume the API client locally using:

```json
"@doc-intelligence/api-client": "workspace:*"
```

### `Makefile`

The Makefile provides one developer-facing command surface across TypeScript and Python:

```bash
make install
make dev
make test
make lint
make typecheck
make format
make check
```

`make dev` delegates to `scripts/dev.sh`. The launcher finds pnpm and uv, starts the React and FastAPI processes together, prints their local URLs, and stops both when `Ctrl+C` is pressed.

### Lockfiles

- `pnpm-lock.yaml` pins JavaScript dependencies.
- `apps/api/uv.lock` pins Python dependencies.

Both lockfiles should be committed so local development and continuous integration install the same dependency graph.

### `.env.example`

This file documents expected configuration without storing secrets. Developers copy it to `.env`; the real `.env` file is ignored by Git.

### `.github/workflows/ci.yml`

Continuous integration checks formatting, linting, static types, tests, and the frontend production build on pull requests and pushes to `main`.

## Generated directories

The following directories are generated locally and excluded from Git:

```text
node_modules/       JavaScript dependencies
.venv/              Python virtual environment
dist/               Production build output
coverage/           Test coverage output
.pytest_cache/       Pytest cache
.ruff_cache/         Ruff cache
__pycache__/         Compiled Python bytecode
```

They are not part of the source architecture and should not be committed.

## Dependency direction

The intended high-level dependency direction is:

```text
React pages and features
          ↓
TypeScript API client
          ↓ HTTP
FastAPI routes
          ↓
Application services
          ↓
Domain interfaces
          ↓
Provider and repository adapters
          ↓
External infrastructure
```

Dependencies should flow downward through these boundaries. React must not access Supabase, Gemini, or Unstructured directly, and backend route handlers should not accumulate document-processing or persistence logic.
