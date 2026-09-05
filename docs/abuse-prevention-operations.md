# Abuse-prevention operations

This runbook covers the demo-ready Phase 10C controls: application capability switches,
request admission limits, durable request and provider-attempt budgets, short automatic
provider circuits, and sanitized usage telemetry. It does not replace provider-side quotas.

External/server alert delivery and provider-dashboard alert configuration are intentionally
deferred until production readiness. Quota-exhaustion and provider-key rotation rehearsals are
also deferred so this demo-readiness pass does not consume limited provider quota.

## Before running a controlled demo

1. Apply the latest database migration with `make db-migrate`.
2. Set every capability and quota variable explicitly in the deployed API environment.
3. Generate a private `IP_HASH_SALT` of at least 32 random characters. Do not reuse an API key
   or commit the value.
4. Keep the demo supervised. Production TLS/CORS validation, alert delivery, and provider-side
   alert configuration remain production-readiness work.

The values in `.env.example` are conservative starting points, not capacity promises. Lower
global budgets for the first test and raise them only after observing normal use.

## Capability switches

| Capability     | API environment variable           | When disabled                                                                          |
| -------------- | ---------------------------------- | -------------------------------------------------------------------------------------- |
| Sign-up UX     | `PUBLIC_SIGNUP_ENABLED=false`      | The sign-up form is disabled. Also disable registrations in Supabase Auth.             |
| Upload intake  | `UPLOADS_ENABLED=false`            | New uploads return `503`; existing documents remain readable.                          |
| New processing | `PROCESSING_ENABLED=false`         | Accepted uploads are retained without scheduling processing, and retries return `503`. |
| Manual retries | `PROCESSING_RETRIES_ENABLED=false` | Retry requests return `503`; other processing policy is unchanged.                     |
| Questions      | `ASK_ENABLED=false`                | Ask requests return `503`; document browsing remains available.                        |

Change the environment variable and restart or redeploy the API. The server is authoritative;
the UI reads `GET /api/v1/capabilities` only to present the state clearly.

`PUBLIC_SIGNUP_ENABLED` alone cannot stop direct requests to Supabase Auth because the browser
uses the public Supabase endpoint. To close registration authoritatively, disable new-user
signups in the Supabase project's Authentication settings as well.

## Verify a switch

After restart, inspect the public capability response:

```bash
curl --fail --silent http://localhost:8000/api/v1/capabilities
```

Then make one authenticated request to the disabled operation. It must return `503` with a
stable `code` such as `uploads_disabled` or `ask_disabled`, and it must not schedule background
work or contact a provider. The automated API tests verify this without provider credentials.

## Quota behavior

- User and IP short-window rejections return `429 Too Many Requests`.
- Global safety-budget exhaustion returns `503 Service Unavailable` without exposing the
  configured account-wide limit.
- Each real Unstructured job submission and Gemini extraction, embedding, or answer attempt is
  reserved immediately before the HTTP call. Adapter retries consume additional attempt units.
- A cluster of network, `429`, or retryable `5xx` outcomes opens a short circuit for only that
  provider operation. Circuits are per API process; durable daily budgets remain authoritative
  across processes.
- Responses include a stable `code` and `Retry-After` when a fixed window has a known reset.
- Upload acceptance reserves document and byte capacity atomically. Invalid, duplicate, or
  failed-before-acceptance uploads compensate that reservation; the request-rate unit remains
  consumed.
- Retry requests have both user limits and a per-document five-minute cooldown by default.
- The API hashes the direct peer IP with HMAC-SHA256 and never persists the raw address. Do not
  trust `X-Forwarded-For` until the deployment's proxy chain is explicitly configured.

Quota counters, usage events, and the future alert-deduplication table are backend-only tables
with RLS enabled and no browser policies. The application service-role connection is the only
normal writer. No alert sink is active in the demo configuration.

## Inspect sanitized usage

Use the Supabase SQL editor or a read-only database session. These examples contain internal
IDs and hashes, never emails, filenames, document text, tokens, or provider bodies:

```sql
select action, outcome, code, count(*)
from public.usage_events
where created_at >= now() - interval '24 hours'
group by action, outcome, code
order by count(*) desc;

select subject_type, metric, used, window_start, window_seconds
from public.quota_counters
order by updated_at desc
limit 100;
```

The schema and service boundary retain deduplication support for future 70%, 90%, and 100%
alerts, but alert emission is inactive for the demo. A delivery integration must be chosen and
tested before unattended public operation.

## Zero-provider-call verification

Run the deterministic safeguard suites while Gemini and Unstructured credentials are absent or
unused:

```bash
cd apps/api
.venv/bin/pytest -m 'not integration' \
  tests/test_safeguards.py \
  tests/test_capabilities_api.py \
  tests/test_documents_api.py \
  tests/test_queries_api.py \
  tests/test_gemini_providers.py \
  tests/test_unstructured_parser.py
```

These tests use in-memory repositories and `httpx.MockTransport`. They verify upload and ask
kill switches, typed limit responses, per-operation budgets, retry accounting, and circuit
opening without contacting either provider. Ownership tests elsewhere in the API suite verify
that one account cannot list, retrieve, retry, or query another account's documents. The web
suite verifies disabled signup/upload/retry/ask states.

## Retention cleanup

The maintenance command is read-only unless `--apply` is selected through the Make target.
The default retention period is 30 days:

```bash
make safeguards-cleanup-dry-run
make safeguards-cleanup-apply
```

Override it explicitly when needed:

```bash
RETENTION_DAYS=90 make safeguards-cleanup-dry-run
```

The apply command removes only expired quota buckets and old alert/usage telemetry. It does
not delete users, documents, storage objects, extraction results, or query records.

## Incident: suspected abuse

1. Disable the smallest affected capability and restart/redeploy.
2. For signup abuse, also disable Supabase registrations.
3. Confirm the block through the capability endpoint and one direct API request.
4. Review sanitized usage by internal user ID and hashed IP bucket.
5. Check Gemini and Unstructured usage dashboards and provider status.
6. Suspend an abusive profile if needed; do not delete evidence during investigation.
7. Re-enable with lower global limits and one synthetic request only after the cause is known.

Provider-key rotation rehearsal and deliberate quota exhaustion are production-readiness tasks,
not part of the current demo verification. The emergency switches above remain available if a
problem is observed during a supervised demo.

## Rollback

The migration only adds safeguard tables, so the preceding application version can ignore
them. Prefer disabling affected capabilities and deploying a corrected version. Do not drop
counter tables during an incident; they provide useful evidence and do not expose corpus
content.
