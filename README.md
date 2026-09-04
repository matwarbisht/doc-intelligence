# Document Intelligence

A general-purpose document intelligence platform that turns heterogeneous documents into canonical elements, retrieval-ready chunks, semantic facts, and cited answers.

## Repository

- `apps/web` — React, TypeScript, and Vite frontend
- `apps/api` — FastAPI backend
- `packages/api-client` — frontend API-client boundary
- `supabase` — database migrations and local configuration
- `docs` — architecture and engineering decisions
- `examples` — safe sample documents

## Prerequisites

- Node.js 22 or newer
- pnpm 10
- uv

If uv is installed in its default user location, ensure `$HOME/.local/bin` is on your `PATH`.

## Setup

```bash
make install
cp .env.example .env
make dev
```

The frontend runs at <http://localhost:5173>, the API at <http://localhost:8000>, and API documentation at <http://localhost:8000/docs>. Local development also accepts the equivalent `127.0.0.1` frontend origin.

`make dev` starts both applications, detects uv in its standard user installation location, and supports pnpm installed through Volta or Corepack. Press `Ctrl+C` once to stop both servers.

For the complete local product workflow, start Supabase and inject its local credentials without writing them to `.env`:

```bash
make db-start
make dev-local
```

## Commands

```bash
make dev          # Run frontend and API
make test         # Run tests
make lint         # Run linters
make typecheck    # Run static type checks
make format       # Format the codebase
make check        # Run every verification step
```

Stage 1 focuses on a complete upload-to-cited-answer vertical slice. Authentication, billing, multi-tenancy, distributed queues, and dedicated search infrastructure are deferred.

## Documentation

- [Engineering decision log](decisions.md)
- [Stage 1 implementation plan](docs/implementation-plan.md)
- [Architecture](docs/architecture.md)
- [Database model](docs/database.md)
- [Document upload and lifecycle](docs/document-lifecycle.md)
- [Parsing and canonicalization](docs/parsing-pipeline.md)
- [Semantic enrichment and indexing](docs/semantic-enrichment.md)
- [Retrieval and cited answers](docs/retrieval-and-cited-answers.md)
- [Design system](docs/design-system.md)
- [Repository structure](docs/repository-structure.md)
