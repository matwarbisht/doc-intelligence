# Deployment guide

Phase 7 makes the MVP deployable without choosing a hosting vendor. The intended
shape is a static web container, one FastAPI container, a hosted Supabase project,
and the configured Unstructured and Gemini services.

## Build the containers

From the repository root:

```bash
docker build -f apps/api/Dockerfile -t doc-intelligence-api apps/api
docker build \
  -f Dockerfile.web \
  --build-arg VITE_API_URL=https://api.example.com \
  -t doc-intelligence-web .
```

`VITE_API_URL` is compiled into the browser bundle. It must be the public API URL
and must never contain a credential. Rebuild the web image when this URL changes.

## Vercel frontend

Configure the Vercel project's Root Directory as `apps/web`. The committed
`apps/web/vercel.json` rewrites requests that do not resolve to static files to
`/index.html`, allowing React Router to handle direct visits and browser refreshes
for routes such as `/sign-in`, `/documents`, and `/style-guide`.

This is an internal rewrite rather than a redirect: the requested URL remains in
the address bar. A new deployment is required after changing the routing config.

## API environment

Set these secrets and environment-specific values on the API service:

```text
APP_ENV=production
LOG_LEVEL=INFO
LOG_FORMAT=json
CORS_ORIGINS=https://app.example.com
DATABASE_URL=postgresql://...
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_STORAGE_BUCKET=documents
UNSTRUCTURED_API_KEY=...
GEMINI_API_KEY=...
```

The remaining model, timeout, retrieval, upload, retry, and extraction-budget
settings have conservative defaults in `.env.example` and can be overridden.
Keep the Supabase service-role key only in the API service.

Use the API liveness endpoint at `/api/v1/health`. Both images also define
container health checks. Application logs can be emitted as one JSON object per
line with `LOG_FORMAT=json`; every HTTP response includes an `x-request-id` that
is also attached to logs written during that request.

## Database migrations

Create and link the intended hosted Supabase project using the Supabase CLI, then
review and apply the committed migrations:

```bash
./scripts/supabase.sh link --project-ref <project-ref>
./scripts/supabase.sh db push --dry-run
./scripts/supabase.sh db push
```

Do not run `db reset` against a hosted project. It is a destructive local
development command.

## Runtime constraints

Processing currently starts as a FastAPI background task and uses Postgres jobs
as its durable state. Deploy the API as a long-lived process with graceful
shutdown, and begin with one replica. Serverless request runtimes may terminate
work after returning the upload response; multiple replicas also need a separate
worker/claim loop to guarantee queued work is picked up. A dedicated worker and
managed queue are intentionally deferred until usage justifies them.

Provider-specific manifests, DNS, TLS, preview environments, autoscaling, and
continuous deployment remain undecided. Choose those only after selecting a host;
the two containers and environment contract are the portable boundary.
