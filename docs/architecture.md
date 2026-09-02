# Architecture

The Stage 1 MVP is a modest monorepo with independently deployable frontend and backend applications.

```text
React client
    ↓ HTTP
FastAPI application
    ↓
Application services
    ↓
Provider and repository interfaces
    ↓
Supabase, Unstructured, and Gemini
```

## Dependency boundaries

- HTTP routes validate transport data and call application services.
- Application services coordinate document-processing use cases.
- Domain models do not depend on external SDKs.
- Provider adapters contain Unstructured, Gemini, and storage integrations.
- Repository adapters contain database persistence logic.
- The frontend consumes a generated client derived from FastAPI's OpenAPI schema.

## Stage 1 lifecycle

```text
UPLOADED → QUEUED → PARSING → EXTRACTING → EMBEDDING → INDEXING → READY
```

Failed stages retain their specific state and can be retried. The first worker may be lightweight, but the HTTP contract remains asynchronous.
