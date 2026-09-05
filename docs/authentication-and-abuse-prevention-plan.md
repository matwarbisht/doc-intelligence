# Authentication and Abuse-Prevention Implementation Plan

**Status:** Demo-ready scope implemented; production operations explicitly deferred
**Scope:** Post-Stage-1 MVP hardening for a controlled demo
**Last updated:** September 5, 2026

## 1. Purpose

Before Phase 10, Document Intelligence behaved as a single-user application: every API caller
could upload, list, inspect, process, retry, and query the same corpus. Phases 10A and 10B now
establish identity, isolate user-owned data, and enforce ownership at the database boundary.
The implemented safeguards address sustained consumption of project-owned Unstructured and
Gemini quotas during a controlled demo.

### Demo-ready scope decision

The application controls in this plan are implemented and verified without real provider
traffic: authentication and ownership, request admission limits, hard provider-attempt budgets,
manual capability switches, sanitized telemetry, and short automatic provider circuits.

Server/external alert delivery, provider-dashboard alerts, production TLS/CORS validation,
deliberate quota-exhaustion testing, and provider-key rotation rehearsal are deferred until the
product is being made production-ready. The alert schema and interface remain as extension
points, but no alert sink is active in the current application wiring. This means the current
state is suitable for a supervised demo, not unattended public production traffic.

This phase will add:

- Public email-and-password registration and sign-in through Supabase Auth.
- User-owned documents and query history.
- Server-side authorization on every corpus operation.
- Per-user, per-IP, and global limits for expensive actions.
- Automatic provider-budget circuit breakers.
- Manual kill switches for signups, uploads, processing, retries, and questions.
- Operator-inspectable sanitized usage and response runbooks.
- An identity model that can later support verified email, password recovery, magic links,
  OAuth, account linking, workspaces, and administrative tooling.

The goal is safe early testing, not a complete enterprise identity, billing, or abuse platform.

## 2. Confirmed product choices

These choices should be treated as the starting constraints for implementation:

1. Registration is initially public rather than invite-only.
2. The first authentication method is email plus password.
3. Email verification, magic links, password-reset email, and OAuth are deferred.
4. Each account receives a private document corpus. A user must never retrieve, inspect,
   retry, or query another user's documents.
5. Provider secrets remain available only to the API process.
6. Automatic limits are the primary protection. Alerts inform the operator; kill switches are
   the emergency control.
7. No admin panel is required for the first release. Deployment configuration, Supabase's
   dashboard, documented SQL/CLI procedures, and provider dashboards are the operator
   interfaces.
8. Provider integrations remain behind the existing application-owned boundaries.
9. Existing local and hosted documents must be assigned to an owner instead of being silently
   deleted or exposed to the first user who signs in.

## 3. Threat model

### 3.1 Risks in scope

- A user repeatedly uploads valid files to consume Unstructured pages and Gemini tokens.
- A user creates multiple accounts to bypass per-user limits.
- A user submits several large documents or batches and fills the processing queue.
- A user repeatedly retries a document that is failing because of provider throttling.
- A user repeatedly asks questions to consume query-embedding and answer-generation calls.
- A caller bypasses the frontend and invokes the API directly.
- A caller changes a document UUID or query scope to access another user's corpus.
- A leaked browser session is used until it expires or is revoked.
- A provider outage or `429` response triggers repeated retries that amplify consumption.
- Logs or error responses expose credentials, document contents, raw provider responses, or
  personally identifying information.
- The operator does not see a provider billing alert quickly enough to intervene manually.

### 3.2 Risks deliberately deferred

- Enterprise SSO, SCIM, organization policies, and role-based administration.
- Shared workspaces and document-level sharing.
- Sophisticated bot and device-fingerprint detection.
- Payment collection and customer billing.
- Content moderation and malware scanning beyond existing file validation.
- Distributed rate limiting across many regions.
- A full security information and event management platform.
- Automated account merging based on matching email addresses.

## 4. Security and architecture principles

### 4.1 Authentication is not authorization

Supabase Auth will prove who the caller is. Application services and repositories must still
enforce which records that identity may use. A valid token must never grant access to the
global corpus by default.

### 4.2 The API is the authorization boundary

UI controls are usability aids, not security controls. Every upload, list, detail, retry, and
query endpoint must authenticate and authorize independently. CORS does not replace either
control.

### 4.3 Ownership uses immutable user IDs

Application rows will reference `auth.users.id`, not email addresses. Emails can be changed,
verified, reused, or returned differently by future identity providers. A stable UUID lets new
login methods attach to the same account without rewriting document ownership.

### 4.4 Ownership is stored at aggregate boundaries

`documents.owner_id` will own the document aggregate. Document versions, processing jobs,
elements, chunks, embeddings, extraction runs, entities, facts, and relationships already
lead back to a document and should derive ownership through those foreign keys. Duplicating
`owner_id` across every derived table would increase inconsistency risk.

`queries.user_id` will be stored directly because global questions may not have a
`document_id` from which ownership can be derived.

### 4.5 Limits are enforced atomically and server-side

Checking a counter and incrementing it in separate operations creates a race. Quota
reservation must be an atomic database operation that either reserves capacity or rejects the
request. Expensive provider calls fail closed if their budget cannot be checked.

### 4.6 Concurrency and quotas solve different problems

- Concurrency limits prevent short bursts from overwhelming providers.
- Rate limits constrain request frequency within a short window.
- Daily/monthly quotas constrain sustained consumption.
- Provider spend caps limit financial exposure outside the application.
- Kill switches stop a capability during an incident.

All five layers remain useful.

### 4.7 Account linking must be explicit

Future OAuth identities may be linked to an already authenticated account after
re-authentication or another verified linking flow. Two accounts must never be merged solely
because they report the same email address; a provider's email claim is not by itself proof
that the accounts have the same owner.

## 5. Target architecture

```text
React application
    │
    ├── Supabase Auth: sign up, sign in, refresh, sign out
    │
    └── Bearer access token
             │
             ▼
FastAPI authentication dependency
    │  verifies signature, issuer, audience, expiry
    │
    ├── CurrentUser(user_id, session metadata)
    ├── Feature/kill-switch guard
    ├── Per-user and per-IP rate-limit guard
    ├── Atomic quota reservation
    └── Ownership-aware application service
             │
             ├── Postgres repositories scoped by user_id
             ├── Private Supabase Storage
             ├── Provider budget gate → Unstructured
             └── Provider budget gate → Gemini
```

## 6. Identity and session design

### 6.1 Supabase Auth responsibilities

Supabase Auth will own:

- Password hashing and credential verification.
- Access and refresh token issuance.
- Session refresh and revocation.
- Email/password identity records.
- Future email confirmation, magic-link, recovery, and OAuth identities.

The application database must not contain passwords, password hashes, refresh tokens, or
copies of provider credentials.

### 6.2 Application profile

Add `public.profiles`:

| Column                     | Purpose                                                                       |
| -------------------------- | ----------------------------------------------------------------------------- |
| `user_id uuid primary key` | References `auth.users(id)` and is the application identity.                  |
| `status text`              | `active` or `suspended`; blocks application access without deleting identity. |
| `display_name text null`   | Optional presentation field; not an authorization identifier.                 |
| `created_at timestamptz`   | Audit timestamp.                                                              |
| `updated_at timestamptz`   | Audit timestamp.                                                              |

A new-auth-user database trigger may create the profile, provided it is small, deterministic,
and covered by a migration test. The API should also tolerate and repair a missing profile so
a trigger failure does not create an irrecoverable user.

### 6.3 Initial signup policy

- Email/password signup is enabled publicly.
- Email confirmation is not required during the limited test.
- Password policy is configured in Supabase, with sensible minimum length and compromised
  password protection where the selected plan supports it.
- The UI explains that the environment is an early test and users must upload only data they
  are permitted to process.
- Suspended users receive a generic `403` response and cannot use expensive or corpus APIs.

Because the browser must know the public Supabase URL and publishable/anonymous key, a
frontend-only `PUBLIC_SIGNUP_ENABLED=false` flag cannot prevent a determined caller from
calling Supabase Auth directly. The authoritative signup kill procedure must also disable new
registrations in the Supabase project. A future pre-user-creation hook or server-controlled
invitation flow can make this application-controlled and instantaneous.

### 6.4 API token verification

Create one `CurrentUser` FastAPI dependency that:

1. Requires `Authorization: Bearer <access-token>`.
2. Initially asks Supabase Auth's `/auth/v1/user` endpoint to validate the session. This works
   consistently with both the local HS256 stack and hosted signing-key configurations.
3. Leaves that check behind an application-owned provider boundary so hosted deployments can
   later adopt cached JWKS verification without changing routes or services.
4. Parses `sub` as the authenticated UUID.
5. Loads the application profile and rejects suspended users.
6. Returns a small application-owned identity object rather than leaking provider token
   payloads into services.

Token contents and authorization headers must never be logged. A rejected token returns `401`,
an unavailable auth service returns `503`, and an authenticated but suspended or unauthorized
caller returns `403` or an ownership-safe `404` as described below. If hosted traffic makes the
validation round trip material, add cached signing-key verification with bounded JWKS refresh.

### 6.5 Frontend session behavior

- Add sign-up and sign-in screens using the existing design system.
- Add an auth provider that restores the current session before rendering protected routes.
- Attach the current access token inside `packages/api-client`, which is already the intended
  authentication-header boundary.
- Refresh sessions through the Supabase client and retry one API request after a successful
  refresh, but never create an unbounded `401` retry loop.
- Protect `/documents`, document details, and `/ask` routes.
- Add sign out and a compact account affordance.
- Clear user-specific TanStack Query caches on sign out or account change.
- Never place service-role, Gemini, or Unstructured credentials in the browser bundle.

### 6.6 Future identity enhancements

The first implementation should leave these extensions open without implementing them:

- Email confirmation by enforcing `email_confirmed_at`/equivalent session state.
- Password recovery using the provider's recovery link flow.
- Magic-link authentication.
- OAuth identities linked to the same immutable user ID.
- Explicit identity linking from an authenticated account settings screen.
- Administrative account suspension and audit history.
- Workspaces and memberships layered above personal ownership.

## 7. Data-model migration

### 7.1 Ownership columns

Add:

```text
documents.owner_id uuid → auth.users.id
queries.user_id    uuid → auth.users.id
```

Target constraints and indexes:

- `documents.owner_id` is ultimately `not null`.
- Replace global `documents.content_hash unique` with
  `unique (owner_id, content_hash)` so different users can upload the same bytes without
  learning that another user already has them.
- Add `documents_owner_created_idx (owner_id, created_at desc, id desc)`.
- `queries.user_id` is ultimately `not null`.
- Add `queries_user_created_idx (user_id, created_at desc)`.
- A document-scoped query must reference a document owned by the same user; enforce this in
  the service/repository transaction, and consider a composite database relationship only if
  it simplifies rather than duplicates ownership constraints.

### 7.2 Storage paths

New originals should use an auditable tenant prefix such as:

```text
users/<user-id>/documents/<document-id>/<sanitized-filename>
```

The stored `storage_path` remains authoritative. Existing objects do not need to be moved
during the ownership migration if their private paths remain valid; moving them creates an
avoidable data-loss window. A later maintenance task may normalize legacy paths.

### 7.3 Expand–backfill–enforce rollout

Do not add required ownership columns in one destructive migration.

1. **Expand:** add nullable `owner_id` and `user_id`, indexes, profiles, quota tables, and new
   repository methods while the old application is still readable.
2. **Create owner:** create or identify the operator's Supabase Auth account and record its
   UUID explicitly.
3. **Backfill:** run a one-time, transactional command that assigns all pre-auth documents and
   queries to that UUID. Print counts before and after; abort on an unknown owner.
4. **Verify:** assert there are no orphan documents, queries, or invalid document-scoped
   queries.
5. **Enforce:** make ownership columns non-null and replace the global hash constraint.
6. **Deploy:** release the ownership-aware API and frontend together.

The backfill owner UUID must not be hard-coded in a committed migration. Local seed data may
use a deterministic test identity created by the supported Supabase seed process.

### 7.4 Row-level security

All existing public tables already have RLS enabled without browser policies. The current API
uses the Supabase service role, which bypasses RLS; therefore RLS must not be presented as the
primary protection for API repository bugs.

- Primary enforcement: every backend query scopes through the authenticated `user_id`.
- Defense in depth: add owner-based policies for `profiles`, `documents`, and `queries`, and
  ownership-through-parent policies for derived tables if browser-direct access is introduced.
- Keep direct browser access to document tables disabled during this phase.
- Test that the anonymous and ordinary authenticated database roles cannot read records
  through unintended policies.

## 8. Authorization changes by workflow

### 8.1 Upload

1. Authenticate the user and ensure the profile is active.
2. Check the uploads kill switch.
3. Enforce short-window user/IP limits.
4. Validate filename, type, and size.
5. Atomically reserve daily document and byte quotas.
6. Deduplicate only within the owner's corpus.
7. Store under the owner-prefixed path.
8. Create the owner-scoped document and processing job.
9. Release or compensate the reservation if persistence/storage fails before acceptance.

### 8.2 Document list and detail

- List only `where owner_id = current_user.id`.
- Fetch detail using both document ID and owner ID.
- Return `404`, not `403`, when a document exists for another user so its existence is not
  disclosed.
- Include only processing and intelligence records derived from the authorized document.

### 8.3 Retry processing

- Resolve the document by `(document_id, owner_id)` before scheduling work.
- Check retry and processing switches independently.
- Enforce per-document cooldown, per-user short-window rate limit, and per-day retry quota.
- Reject retries for a document already queued or running.
- Continue to use bounded provider retries; an HTTP request retry must not reset application
  quota or processing-attempt history.

### 8.4 Global and document-scoped questions

- Global retrieval must add `documents.owner_id = current_user.id` to keyword, semantic, and
  structured branches before fusion.
- Document-scoped retrieval must require both the selected ID and the same owner ID.
- Persist `queries.user_id` for global and scoped questions.
- Check the ask switch, request rate, and daily question budget before generating a query
  embedding.
- Preserve the existing no-evidence behavior so Gemini is not called unnecessarily.

### 8.5 Background processing

Background jobs must carry both `document_id` and expected `owner_id`, or re-read ownership
from the document before each costly stage. They must not depend on an expired browser token.
Provider usage must still be attributed to the owning user when the work runs asynchronously.

## 9. Rate limiting

### 9.1 Limit dimensions

Use layered keys:

- Authenticated user ID for ordinary application limits.
- Hashed source IP for signup-related and account-farming resistance.
- Document ID for retry cooldowns.
- Global scope for protecting shared provider accounts.

Do not store raw IP addresses indefinitely. Hash a normalized address with a rotating,
server-side salt. Configure trusted reverse proxies explicitly before accepting forwarded IP
headers; otherwise use the direct peer address.

### 9.2 Initial configurable policy

The following are conservative starting values, not permanent product promises:

| Action            | User limit          | IP/global supplement                        |
| ----------------- | ------------------- | ------------------------------------------- |
| Upload request    | 10/hour             | 30/hour/IP                                  |
| Files accepted    | 25/day              | Global daily document budget                |
| Uploaded bytes    | 250 MB/day          | Global daily byte budget                    |
| Ask request       | 30/hour and 100/day | 120/hour/IP plus global daily answer budget |
| Retry request     | 5/hour and 10/day   | One retry/document/5 minutes                |
| Active processing | 3/user              | Existing global processing concurrency      |
| Stored documents  | 100/user            | Configurable global storage ceiling         |

Every value must be configuration-driven and documented in `.env.example`. Production
defaults should be safe when a variable is omitted.

### 9.3 Persistence design

Add durable fixed-window counters, for example `quota_counters`:

| Column           | Purpose                                                     |
| ---------------- | ----------------------------------------------------------- |
| `subject_type`   | `user`, `ip`, or `global`.                                  |
| `subject_key`    | UUID, salted hash, or a constant global key.                |
| `metric`         | Uploads, bytes, questions, retries, provider attempts, etc. |
| `window_start`   | Canonical UTC window boundary.                              |
| `window_seconds` | Makes hourly and daily counters explicit.                   |
| `used`           | Atomic consumed/reserved quantity.                          |
| `updated_at`     | Operations and cleanup.                                     |

The composite primary key is `(subject_type, subject_key, metric, window_start,
window_seconds)`. A Postgres function or single conditional upsert must increment only when
`used + requested <= limit`, returning the remaining amount. This remains correct across
concurrent API workers.

Old buckets can be deleted by a periodic maintenance command. A future Redis limiter may
replace short windows at higher traffic, while durable daily provider budgets stay in
Postgres.

### 9.4 HTTP behavior

- Return `429 Too Many Requests` for a user/IP rate or quota rejection.
- Include `Retry-After` when the next eligible time is known.
- Return a stable machine-readable code such as `upload_hourly_limit` or
  `daily_question_budget` plus a safe user message.
- Do not reveal another user's usage or the provider account's exact financial limit.
- Rate-limit failures must not schedule background tasks or invoke providers.

## 10. Provider usage accounting and automatic circuit breakers

### 10.1 Why application accounting is required

Provider dashboards and billing alerts may be delayed. Concurrency limits do not stop a
single user from consuming quota over several hours. Before each expensive provider attempt,
the application must reserve capacity against a configured global budget.

### 10.2 Metrics to record

At minimum, attribute these metrics to both user and global scopes:

- Unstructured job submissions/attempts.
- Unstructured pages processed when the result exposes a reliable page count.
- Gemini extraction attempts and input characters/chunks.
- Gemini embedding attempts and number of embedded chunks.
- Gemini query-embedding attempts.
- Gemini answer-generation attempts.
- Provider `429` and retryable `5xx` responses.
- Successful, failed, and rejected operations.

Count provider attempts, including internal retries, because rejected requests may still
consume provider quota even when they do not incur token charges. Record token/page usage
when providers return it, but do not delay enforcement if exact billing units are unavailable.

### 10.3 Enforcement points

- Reserve an Unstructured unit immediately before submitting a provider job.
- Reserve extraction capacity immediately before each Gemini extraction attempt.
- Reserve embedding capacity per provider batch/call.
- Reserve query and answer capacity separately because a no-evidence query may avoid answer
  generation.
- Reject new work when the global budget is exhausted, regardless of the requesting user's
  remaining personal quota.

### 10.4 Automatic circuit behavior

When a global budget reaches 100%:

- Stop only the affected expensive capability where possible.
- Preserve read-only document list/detail access.
- Return `503 Service Unavailable` with a stable code such as
  `processing_budget_exhausted` and a generic explanation.
- Do not automatically retry until the quota window resets or an operator changes policy.
- Emit one deduplicated critical alert for the threshold/window.

A cluster of provider `429` responses should open a short in-memory circuit for that provider
operation, reducing retry amplification. The durable daily budget remains the authoritative
cross-process protection. Circuit-breaker duration and failure threshold must be bounded and
configurable.

## 11. Kill switches and operator controls

### 11.1 Initial switches

Add independent server configuration:

```env
PUBLIC_SIGNUP_ENABLED=true
UPLOADS_ENABLED=true
PROCESSING_ENABLED=true
PROCESSING_RETRIES_ENABLED=true
ASK_ENABLED=true
```

Each API route must check the relevant server-side switch. The frontend may fetch a small
capabilities response to hide or disable unavailable actions, but the API check is
authoritative.

### 11.2 Invocation without an admin panel

For the first release, an operator invokes switches by changing deployment environment
variables and restarting/redeploying the API. The signup runbook must additionally disable
new-user registration in Supabase because direct Auth requests do not pass through FastAPI.

Document exact host-specific steps after selecting the deployment provider. The generic
runbook must state:

1. Which switch to change.
2. Whether Supabase configuration must also change.
3. Expected user-facing behavior.
4. How to verify the API is blocked.
5. How to re-enable the capability safely.

### 11.3 Capabilities endpoint

Expose a read-only endpoint such as `GET /api/v1/capabilities` containing booleans for signup,
upload, processing retry, and ask availability. It must not expose secret configuration,
quota totals, provider keys, or operator-only reasons.

### 11.4 Future runtime controls

A database-backed operational-controls table and authenticated admin UI may be added when
restart latency becomes operationally unacceptable. That later change requires admin roles,
audit history, CSRF/session protections, and secure recovery from accidental lockout; it is
deliberately excluded from this phase.

## 12. Alerting and monitoring

### 12.1 Thresholds

Emit deduplicated threshold events when user or global daily consumption crosses:

- 70%: warning.
- 90%: high warning.
- 100%: critical and automatically blocked.

Also alert on:

- Repeated signup attempts from one IP bucket.
- A sustained provider `429` rate.
- A sustained provider `5xx` rate.
- Repeated failed retries for the same document.
- An account being suspended.
- Manual kill-switch activation when detectable by the running application.

### 12.2 Delivery abstraction

Introduce an application-owned `AlertSink` boundary:

- `LogAlertSink` is mandatory and emits structured, sanitized events to stdout.
- An optional webhook/email adapter can be configured after the deployment platform and
  notification destination are selected.
- Alert delivery failure must not permit an over-budget provider request.
- Store a deduplication record keyed by alert type, scope, and quota window so one threshold
  does not generate an alert on every request.

No document text, filenames, email addresses, auth tokens, provider response bodies, or API
keys should appear in alerts. Use internal user/document/request IDs.

### 12.3 Provider-side controls

Operational setup should include:

- Gemini project-level spend caps and the AI Studio usage/rate-limit dashboard.
- Google Cloud budget threshold emails and, later, Pub/Sub notifications if automated
  infrastructure actions are required.
- Unstructured usage/billing dashboard checks and plan-specific budget limits.
- Unstructured service-status subscriptions only for outages; they are not a substitute for
  account-usage alerts.
- Separate development and public-test provider projects/keys where supported, so a test
  incident cannot consume production capacity.

Provider alerts supplement application enforcement. They are not assumed to be instantaneous
or complete.

## 13. Configuration contract

Group new configuration by purpose and validate every positive numeric limit at startup.
Suggested names:

```env
# Authentication
SUPABASE_JWT_ISSUER=
SUPABASE_JWT_AUDIENCE=authenticated
PUBLIC_SIGNUP_ENABLED=true

# Feature controls
UPLOADS_ENABLED=true
PROCESSING_ENABLED=true
PROCESSING_RETRIES_ENABLED=true
ASK_ENABLED=true

# Per-user limits
USER_UPLOADS_PER_HOUR=10
USER_DOCUMENTS_PER_DAY=25
USER_UPLOAD_BYTES_PER_DAY=262144000
USER_ASKS_PER_HOUR=30
USER_ASKS_PER_DAY=100
USER_RETRIES_PER_HOUR=5
USER_RETRIES_PER_DAY=10
USER_MAX_ACTIVE_JOBS=3
USER_MAX_DOCUMENTS=100
RETRY_COOLDOWN_SECONDS=300

# IP limits
IP_UPLOADS_PER_HOUR=30
IP_ASKS_PER_HOUR=120
IP_HASH_SALT=

# Global safety budgets
GLOBAL_DOCUMENTS_PER_DAY=
GLOBAL_UPLOAD_BYTES_PER_DAY=
GLOBAL_UNSTRUCTURED_ATTEMPTS_PER_DAY=
GLOBAL_GEMINI_EXTRACTIONS_PER_DAY=
GLOBAL_GEMINI_EMBEDDING_CALLS_PER_DAY=
GLOBAL_GEMINI_ANSWERS_PER_DAY=

# Provider circuits
PROVIDER_CIRCUIT_FAILURE_THRESHOLD=5
PROVIDER_CIRCUIT_COOLDOWN_SECONDS=60

# Optional alert delivery
ALERT_WEBHOOK_URL=
```

Blank global budgets must have an explicit interpretation. In production, choose either
startup failure or documented safe defaults; do not silently interpret a missing budget as
unlimited. Tests and local development may use a clearly named unrestricted profile.

## 14. API and client contract changes

### 14.1 API responses

Standardize error bodies sufficiently for UI decisions:

```json
{
  "detail": "Daily question limit reached.",
  "code": "daily_question_limit",
  "retry_after_seconds": 21600
}
```

Expected status classes:

- `401`: missing, expired, or invalid session.
- `403`: suspended account or authenticated capability prohibition.
- `404`: document absent or not owned by the caller.
- `409`: already processing or another state conflict.
- `429`: caller/IP rate or quota exceeded.
- `503`: feature disabled, global budget exhausted, or provider circuit open.

### 14.2 API client

- Centralize bearer-token injection in `packages/api-client`.
- Preserve typed error codes and retry timing.
- Do not automatically retry `401`, `403`, `404`, `409`, or quota-related `429` responses.
- TanStack Query polling must stop on authorization, suspension, disabled features, and hard
  quota errors.

### 14.3 UI behavior

- Sign-up/sign-in forms use existing tokens and components.
- Disabled features show a calm, specific explanation without disclosing provider budgets.
- Quota errors retain selected files/questions where safe so the user does not lose input.
- The upload queue distinguishes user-limit rejection from provider-processing failure.
- The account area supports sign out and displays the signed-in email for orientation only.
- Do not build a quota dashboard or admin panel in this phase.

## 15. Implementation phases

Every phase should be independently testable and keep the application runnable.

### Phase A — Record contracts and test fixtures

- Add the final decisions to `decisions.md` before implementation.
- Define `CurrentUser`, authorization errors, limit metrics, feature switches, and stable error
  codes as application-owned types.
- Add deterministic test users Alice, Bob, suspended user, and operator/backfill user.
- Decide production quota values and operator alert destination before enabling public signup.

**Exit criteria:** The ownership, public-signup, quota, and operational-control policies have
unambiguous tests and configuration names.

### Phase B — Expand the database schema

- Add profiles, nullable ownership columns, indexes, quota counters, and alert deduplication.
- Replace repository method contracts with owner-aware variants.
- Add the atomic quota-reservation database function and concurrency tests.
- Update local seeds without containing real accounts or credentials.

**Exit criteria:** Migrations reset cleanly; old data remains readable for backfill; concurrent
quota reservations cannot exceed a configured limit.

### Phase C — Add authentication transport

- Configure Supabase email/password auth for local and hosted environments.
- Add JWT verification and `CurrentUser` dependency.
- Add sign-up, sign-in, session restoration, token injection, and sign-out UI.
- Protect application routes and clear caches on identity changes.
- Keep health/readiness endpoints public and keep API documentation disabled in production.

**Exit criteria:** Invalid tokens fail; expired sessions refresh once; suspended users are
blocked; secrets never enter the browser bundle or logs.

### Phase D — Enforce corpus ownership

- Scope upload, deduplication, list, detail, processing, retry, all retrieval strategies, and
  query persistence by user ID.
- Add owner-prefixed storage paths for new objects.
- Return ownership-safe `404` responses.
- Add cross-user integration tests for every document and query path.

**Exit criteria:** Alice cannot discover or use Bob's IDs; global ask searches only Alice's
corpus; identical bytes can be uploaded independently by Alice and Bob.

### Phase E — Backfill and contract the schema

- Create/identify the operator account.
- Run the dry-run and transactional ownership-backfill command.
- Verify counts and storage reachability.
- Make owner columns required and replace the global content-hash constraint.
- Document rollback and backup expectations.

**Exit criteria:** No ownerless documents or queries remain, and the operator sees the
pre-auth corpus after signing in.

### Phase F — Add feature switches

- Add validated switch configuration and route/service guards.
- Add the capabilities endpoint and disabled-state UI.
- Write the operator kill-switch runbook, including the separate authoritative Supabase signup
  toggle.

**Exit criteria:** Each expensive capability can be disabled independently and cannot be
bypassed with a direct API request.

### Phase G — Add user/IP rate limits and durable quotas

- Implement atomic reservations and compensation rules.
- Enforce upload, byte, question, retry, active-job, and stored-document limits.
- Add `Retry-After` and typed errors.
- Hash IP identifiers, configure proxy trust, and add counter cleanup tooling.

**Exit criteria:** Parallel requests cannot overshoot limits; another account cannot consume or
inspect a user's allowance; rejected requests never start provider work.

### Phase H — Add provider accounting and circuits (complete)

- Gate each provider attempt, including internal retries.
- Attribute asynchronous processing to the owning user.
- Record sanitized outcome metrics.
- Add operation-specific global budgets and short provider circuits.
- Stop infinite/automatic recovery when a hard budget is exhausted.

**Exit criteria:** A synthetic low budget deterministically blocks the next provider call while
read-only endpoints continue working.

### Phase I — Add alerts and production operational verification (deferred)

- Emit deduplicated 70%, 90%, and 100% structured alerts.
- Implement the chosen external alert sink if one is selected; otherwise document deployment
  log alerts as a release blocker for public testing.
- Configure Gemini caps/budget alerts and verify Unstructured dashboard access.
- Exercise the incident runbooks using test limits and non-sensitive documents.

**Exit criteria for production readiness:** The operator receives a test alert, can identify the
affected capability, can disable it, and can verify that no further provider work starts.

### Phase J — Unattended public/production rollout (deferred)

- Deploy behind TLS with production CORS origins only.
- Use separate public-test provider credentials/projects where possible.
- Start with lower global budgets and raise them only after observing normal usage.
- Create two real test accounts and repeat the cross-user isolation suite manually.
- Verify signup shutdown in both the application and Supabase.
- Document account suspension, provider-key rotation, and incident communication.

**Exit criteria:** Public signup is enabled intentionally, ownership isolation is verified, hard
budgets are active, alerts are delivered, and the operator has rehearsed the shutdown path.

## 16. Testing strategy

### 16.1 Unit tests

- JWT claim validation and current-user conversion.
- Suspended-profile rejection.
- Feature-switch selection.
- Window calculation and retry timing.
- Quota error mapping and `Retry-After` calculation.
- IP normalization and hashing without logging the source value.
- Provider circuit state transitions.
- Alert threshold and deduplication behavior.

### 16.2 Database integration tests

- Profile creation and deletion semantics.
- Expand/backfill/contract migration from a pre-auth fixture.
- Owner-scoped content deduplication.
- Atomic quota reservations under concurrent transactions.
- Ownership joins for keyword, semantic, and structured retrieval.
- Query ownership for global and document-scoped questions.
- Anonymous/authenticated RLS posture.

### 16.3 API integration tests

For every protected route, cover:

- No token.
- Invalid/expired token.
- Active owner.
- Active non-owner.
- Suspended user.
- Disabled feature.
- User rate exhausted.
- Global budget exhausted.

Also verify that a rejected request did not create storage objects, database jobs, queries, or
provider calls.

### 16.4 Frontend tests

- Session loading, sign up, sign in, sign out, and one refresh attempt.
- Protected-route redirects.
- Cache clearing between Alice and Bob.
- Disabled upload/retry/ask controls.
- Typed `429` and `503` messages.
- Upload queue behavior after partial quota rejection.
- Polling termination after suspension or global shutdown.

### 16.5 Adversarial acceptance tests

- Request Bob's document with Alice's valid token.
- Scope Alice's question to Bob's UUID.
- Retry Bob's failed job as Alice.
- Upload identical bytes as two users and verify independent records.
- Send parallel uploads at the last remaining quota unit.
- Create repeated accounts/IP traffic and confirm IP/global layers still constrain cost.
- Disable the UI control and call the API manually.
- Open a provider circuit and verify retries do not amplify calls.
- Sign out Alice, sign in Bob in the same browser, and verify no cached Alice data remains.

## 17. Operations and incident runbooks

Create short executable runbooks for:

### Suspected signup abuse

1. Set the application signup flag off for UX.
2. Disable new registrations in Supabase Auth for authoritative enforcement.
3. Review signup-rate events by hashed IP and internal user IDs.
4. Suspend abusive profiles without deleting evidence immediately.
5. Decide whether to rotate the public URL or enable CAPTCHA/email verification before
   reopening.

### Provider-budget exhaustion

1. Confirm which operation and window opened the circuit.
2. Disable only the affected capability if automatic blocking is insufficient.
3. Check Gemini/Unstructured dashboards and provider response rates.
4. Do not increase limits until normal usage or abuse is understood.
5. Re-enable with a low test budget and one synthetic request.

### Leaked provider credential

1. Disable processing and ask operations.
2. Revoke and replace the affected key at the provider.
3. Update backend secrets and restart the service.
4. Verify no secret is present in logs, images, frontend artifacts, or Git history.
5. Send one synthetic provider request before reopening.

### Leaked user session

1. Revoke the user's sessions through Supabase.
2. Suspend the profile if activity is ongoing.
3. Review internal request IDs and usage events.
4. Re-enable after password reset/recovery is completed.

## 18. Deployment order and rollback

Recommended release order:

1. Back up the hosted database and record Storage object counts.
2. Apply expansion migrations.
3. Create the operator auth account.
4. Backfill and verify ownership.
5. Deploy the auth- and owner-aware API with public signup still disabled.
6. Deploy the authenticated frontend.
7. Apply non-null/unique-constraint enforcement.
8. Configure quotas, alerts, provider caps, and kill-switch runbooks.
9. Test with two accounts.
10. Enable public signup last.

Rollback before ownership enforcement may return to the previous application after disabling
public access. After multiple users have uploaded private data, rolling back to the global
corpus implementation is unsafe because it would expose cross-user records. At that point,
rollback means disabling the affected capabilities and deploying a corrected owner-aware
version—not restoring the pre-auth behavior.

## 19. Definition of done

The controlled-demo scope is complete when:

- A user can register, sign in, restore a session, and sign out with email/password.
- Public signup can be shut down authoritatively.
- Every corpus and processing operation requires a valid, active identity.
- No tested API path exposes or uses another user's documents or derived intelligence.
- Existing documents have an explicit owner.
- Deduplication is per owner.
- Per-user/IP request limits and durable daily quotas are enforced atomically.
- Provider attempts, including retries and background work, respect global budgets.
- Expensive capabilities stop automatically at configured hard limits.
- Manual switches independently disable signup, uploads, processing, retries, and ask.
- CI passes without real provider credentials or paid provider calls.
- `decisions.md`, `.env.example`, architecture, deployment, and operations documentation match
  the implemented behavior.

Before unattended public or production traffic, additionally require operator-visible server
alerts, provider-dashboard alerts/caps where available, production TLS/CORS validation, and
rehearsed shutdown, recovery, quota-exhaustion, and key-rotation procedures.

## 20. Deliberately excluded from this implementation

- Email confirmation and recovery-email delivery.
- Magic links, social OAuth, enterprise SSO, and account-linking UI.
- Automatic account consolidation.
- Organizations, teams, roles, sharing, and collaborative corpora.
- Customer billing or quota purchases.
- A graphical admin console or user-facing usage dashboard.
- CAPTCHA unless signup abuse demonstrates the need before rollout.
- Redis or a distributed queue solely for rate limiting.
- Automated deletion/retention policies and self-service account deletion.
- Provider fallback or an LLM-provider migration.

These omissions keep the phase focused on safe public testing while preserving clear extension
points for later product growth.
