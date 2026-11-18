# M7 — Local Dashboard, Authentication & Observability

This document covers the M7 milestone: the first functional web dashboard for
AgentOps Control Tower, backed by a local (non-federated) authentication
system. It assumes familiarity with the M1–M6 architecture (see the other
documents in this directory and `docs/architecture/telemetry-event-contract.md`).

## 1. Local setup

Prerequisites: PostgreSQL running (see the root `docker-compose.yml`),
`apps/api` installed (`pip install -e "apps/api[dev]"`) with its Alembic
migrations applied (`alembic upgrade head`, run from the repository root with
`-c apps/api/alembic.ini`), and Node.js **20.9+** (Next.js 16 requires it;
Node 18 is not supported).

```bash
# Backend
pip install -e "apps/api[dev]"
alembic -c apps/api/alembic.ini upgrade head
uvicorn agentops_api.main:app --app-dir apps/api/src --reload --port 8010

# Frontend
cd apps/frontend
npm install
cp .env.example .env.local   # starting point - the backend fills in AGENTOPS_API_KEY for you
npm run dev                  # http://localhost:3000
```

> **Zero-config local onboarding (new in the M7 follow-up)**: the steps above
> are now genuinely all you need. The backend auto-bootstraps an initial
> organization/project/environment and an internal API key on first startup
> and writes that key into `apps/frontend/.env.local` for you - no manual
> `bootstrap_admin.py`/`provision_api_key.py` step, and no login, are required
> to see the dashboard with real (if initially empty) data. See section 11 for
> how this works, and section 2 below for the *separate*, still-fully-
> supported path for a real local administrator account.

> **WSL note**: if you run the frontend inside WSL2 against a directory
> mounted from Windows (a `/mnt/c/...` or `/mnt/d/...` path), `next build`
> and `next dev` (both use Turbopack by default in Next.js 16) can crash with
> `Bus error (core dumped)` - a known Turbopack/drvfs incompatibility
> unrelated to this project's code. Work around it by cloning/copying the
> repository onto the Linux filesystem itself (e.g. `~/agentops-control-tower`)
> and running Node commands from there, or by running Node natively on
> Windows instead of inside WSL.

## 2. Bootstrapping the first local administrator

There is no HTTP endpoint for creating a dashboard account, deliberately -
see `apps/api/scripts/bootstrap_admin.py`'s own docstring. It talks to the
database directly, the same way `apps/api/scripts/provision_api_key.py`
already does for organizations and API keys.

```bash
# 1. If you don't already have one, create an organization (and a project):
python apps/api/scripts/provision_api_key.py bootstrap-org \
    --name "Acme Corp" --slug acme --project-name "Default" --project-slug default

# 2. Create the local administrator account for that organization:
python apps/api/scripts/bootstrap_admin.py \
    --organization-id <organization-id> \
    --project-id <project-id>  \
    --email admin@example.com
    # omit --password to be prompted interactively (recommended)

# 3. Provision the server-side API key the dashboard's backend-for-frontend
#    layer will use (see section 5):
python apps/api/scripts/provision_api_key.py create-key \
    --organization-id <organization-id> --project-id <project-id> \
    --name "Dashboard server key"
```

`bootstrap_admin.py` refuses to run if **any** user already exists, unless
you pass `--force` - this is what satisfies "do not recreate an administrator
on every application startup" and "prevent unauthorized users from creating
administrator accounts": the script is the *only* way to create one, it is
never invoked automatically by the application, and running it twice by
accident does not silently create a second admin or reset the first one's
password.

## 3. Authentication architecture

### 3.1 Two separate, independent auth mechanisms

| | Authenticates | Mechanism | Used by |
|---|---|---|---|
| `ApiKey` / `AuthContext` (M5, unchanged) | A *program* | Bearer token, `services/api_key_service.py` | The Python SDK, and the dashboard's own server-side calls to this API |
| `User` / `UserSession` (M7, new) | A *person* | Opaque session token in an HttpOnly cookie | The dashboard's browser-facing login |

**These never interact.** `User.organization_id`/`project_id` are
informational only - they tell the dashboard which tenant this person
belongs to, for display. They are never read by `AuthContext` or
`tenant_scope.py`, and no resource endpoint's authorization logic changed.
Every data request the dashboard makes is still authorized exactly as it was
in M5: by a tenant-scoped API key, via the unmodified `get_auth_context`
dependency.

This is the direct implementation of the M7 requirement to never let a
"internal service identity" bypass `AuthContext`: there isn't one. The
dashboard's server-side layer simply *is* an ordinary API-key-authenticated
client of this backend, like the SDK, with its key configured once per
deployment (`AGENTOPS_API_KEY`, see section 5) rather than once per end user.

### 3.2 Local-auth data model (`apps/api/src/agentops_api/models/core.py`)

- **`User`**: `organization_id` (required), `project_id` (optional,
  narrowing - mirrors `ApiKey`'s own scoping columns), `email` (unique,
  stored lowercased), `password_hash` (Argon2id via `argon2-cffi`), `role`,
  `status`, `last_login_at`.
- **`UserSession`**: `user_id`, `token_prefix` + `token_hash` (SHA-256 of a
  256-bit random token - the same prefix+hash pattern as `ApiKey`, justified
  the same way: the token is high-entropy, not human-chosen, so a slow hash
  buys nothing), `expires_at`, `revoked_at`, `last_seen_at`.

Migration: `apps/api/migrations/versions/8f3a2c1d9e4b_add_users_and_sessions.py`
(chained after M5's `6ecb7214cb1e_add_api_keys.py`). No existing table was
altered.

### 3.3 Password hashing and login (`services/auth_service.py`)

- Argon2id via `argon2-cffi`, used *only* for passwords - the module
  docstring explains why this differs from `ApiKey`'s SHA-256 (a password is
  a low-entropy, human-chosen secret; a session/API-key token is not).
- `authenticate()` raises the same exception, with the same message, for an
  unknown email, a wrong password, and an inactive account - a login failure
  can never be used to enumerate which emails have accounts.
- **Login rate limiting**: an in-memory, per-process sliding window (5
  attempts / 5 minutes per email by default, configurable via
  `Settings.login_rate_limit_max_attempts` / `..._window_seconds`). This is a
  deliberately narrow, no-new-infrastructure choice: the M7 brief's stated
  dev environment mentions a Redis container, but **Redis is not actually
  wired into this repository** (not in `docker-compose.yml`, not read by any
  existing config) - introducing it just for login throttling would be the
  "unnecessary infrastructure" the brief itself warns against. The accepted
  trade-off, which only matters if you run multiple `uvicorn` worker
  processes, is documented in section 9.

### 3.4 Session lifecycle

- `POST /api/v1/auth/login` - verifies credentials, creates a `UserSession`,
  returns the raw token (shown/stored exactly once, like an API key).
- `GET /api/v1/auth/me` - validates a token passed as `X-Session-Token`
  (never a cookie - these endpoints are called server-to-server by the
  Next.js layer, not by the browser; see 4.2).
- `POST /api/v1/auth/logout` - revokes the session.
- Expiration: `Settings.session_ttl_minutes` (default 720 = 12h), enforced in
  `validate_session`. Revocation and expiry are both checked on every
  validation, closing the "prevent session fixation" and "invalidate on
  logout" requirements - a revoked or expired token is indistinguishable
  from an unknown one.

## 4. Browser-to-backend architecture (the trust boundary)

```
Browser  →  Next.js server (this app)  →  FastAPI  →  PostgreSQL
         ←  HttpOnly session cookie only
```

**The browser never talks to FastAPI directly**, and never receives the
session token in any JS-readable form (not in `localStorage`, not in a
non-HttpOnly cookie, not in a JSON response body after login). It only ever
gets an HttpOnly, `SameSite=Lax` cookie (`agentops_session`); `Secure` is set
whenever `NODE_ENV=production`.

### 4.1 Request flow for a protected page

1. `src/proxy.ts` (Next.js 16 renamed `middleware.js` to `proxy.js` - see its
   own doc comment) redirects to `/login` if the session cookie is simply
   *absent*. This is a fast, optimistic UX gate only.
2. The protected route group's layout, `src/app/(dashboard)/layout.tsx`,
   calls `requireUserOrRedirect()` (`src/lib/server/session.ts`), which reads
   the cookie and calls the backend's `GET /api/v1/auth/me` to authoritatively
   re-validate it - catching a cookie that merely *exists* but is expired or
   revoked. This is the actual authorization check for human identity.
3. Once validated, any `/api/*` route handler (`src/lib/server/proxy.ts`'s
   `proxyGet`) that the page's Client Components call repeats step 2, then
   forwards the request to FastAPI using `AGENTOPS_API_KEY` - **never**
   anything from the browser's own request - via `src/lib/server/backend.ts`.

**Nothing the browser sends is ever trusted as a tenant identifier.** A
page's `environment_id`/`agent_id` query parameters only ever *filter* what
the already-authorized API key can already see; they cannot widen it, because
the backend's own `tenant_scope.py` enforces the real boundary independently
of what was asked for.

### 4.2 Why the local-auth endpoints aren't cookie-authenticated

FastAPI's `/api/v1/auth/*` endpoints never read a cookie and have no CSRF
exposure of their own: Next.js calls them server-to-server, passing the
session token explicitly as a JSON field (login/logout) or an
`X-Session-Token` header (`/me`), not as an automatically-attached browser
cookie. CSRF only matters where a browser's cookies are honored, which is
exactly the Next.js boundary - see 4.3.

### 4.3 CSRF

Double-submit cookie: `src/proxy.ts` sets a non-HttpOnly `agentops_csrf`
cookie on first visit (client JS can read it, by design). The login and
logout Route Handlers (`src/app/api/auth/{login,logout}/route.ts`) call
`verifyCsrf()` (`src/lib/server/csrf.ts`), which checks that the cookie's
value matches an `x-csrf-token` request header the client echoes back -
something a cross-site attacker's forged form submission cannot do, since it
can't read the victim's cookie value.

### 4.4 Protected server-side API requests

Every `/api/*` Route Handler under `src/app/api/` (agents, environments,
sessions, executions, traces, dashboard) goes through the shared
`proxyGet()` helper, which (a) requires a valid session, returning 401
otherwise, and (b) is the *only* place `AGENTOPS_API_KEY` is read
(`src/lib/server/env.ts` is guarded with the `server-only` package, so
accidentally importing it from a Client Component fails the build rather
than leaking the key into a browser bundle).

## 5. Environment variables

### Backend (`apps/api`, read from `.env` at the repository root - unchanged from M1-M6)

No new required variables. Two new optional settings with sensible defaults
(`config.py`): `session_ttl_minutes` (720), `login_rate_limit_max_attempts`
(5), `login_rate_limit_window_seconds` (300).

### Frontend (`apps/frontend/.env.local` - see `apps/frontend/.env.example`)

| Variable | Server-only? | Meaning |
|---|---|---|
| `BACKEND_API_URL` | Yes | FastAPI base URL (default `http://localhost:8010`) |
| `AGENTOPS_API_KEY` | Yes | The internal dashboard key. Normally written automatically by the backend's first-run bootstrap (section 11); only provision it by hand via `provision_api_key.py create-key` if you need to override that. **Never** exposed to the browser - read only from `src/lib/server/env.ts`, which is `server-only`-guarded. |
| `LOCAL_AUTH_BYPASS` | Yes | `"true"` skips login entirely for local development (section 11.1). Defaults to off; structurally ignored whenever `NODE_ENV==="production"`, regardless of this value. |

Both are plain (non-`NEXT_PUBLIC_`) variables, so Next.js never inlines them
into the client bundle. The frontend has no other required configuration -
the old, pre-M7 `NEXT_PUBLIC_API_BASE_URL` variable (read by the now-removed
`src/lib/api-client.ts`) is gone, since the browser no longer talks to
FastAPI directly at all.

> The repository also has `apps/frontend/env.local` (no leading dot) -
> pre-existing, committed, and **not** a file Next.js actually loads (it only
> reads `.env.local`, `.env.development.local`, etc. - names with a leading
> dot). It was already dead configuration before M7 (its one variable,
> `NEXT_PUBLIC_API_BASE_URL`, was only ever used by the code this milestone
> removes) and is left as-is rather than touched, since renaming or deleting
> tracked, unrelated files was out of scope for this milestone.

## 6. Dashboard architecture

- **Stack**: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4.
  No new UI library, state-management library, or data-fetching library was
  added - all additions were standard Next.js primitives (Route Handlers,
  `proxy.ts`, Server Components) plus `server-only` (for the reason above).
- **Route group**: every authenticated page lives under
  `src/app/(dashboard)/` (Overview, Agents + detail, Executions + detail,
  Sessions + detail, Traces + detail, Environments + detail, Settings, and
  the pre-existing `integrations` page, moved here so it too gets a session
  and isn't the one page left unprotected). `/login` is a sibling, outside
  the group, with no sidebar/shell.
- **Centralized API client** (`src/lib/api/client.ts`): every Client
  Component fetches through here, never via a raw `fetch` to a backend URL -
  and always against this app's own `/api/*` routes. Typed response shapes
  live in `src/lib/types.ts`, hand-kept in sync with the backend's Pydantic
  schemas (there is no cross-language codegen in this project).
- **Shared UI**: `src/components/ui/` (`StatusBadge`, `LoadingSkeleton`,
  `EmptyState`, `ErrorState`, `Pagination`) and
  `src/components/telemetry/event-row.tsx` (one event's rendering, reused by
  both the execution-detail timeline and the trace tree view).
- **Timeline/trace rendering** (`src/lib/timeline.ts`): sorts events
  chronologically, derives a duration for events that don't carry
  `duration_ms` themselves (the execution-level started/completed pair never
  does - see `execution.py`'s `_terminal_event`) by matching same-`span_id`
  counterparts, and computes a display depth from the `parent_span_id` chain
  - never inventing a relationship an event's own identifiers don't
  establish (an orphaned `parent_span_id` not present in the fetched set is
  shown at depth 0, not guessed at).
- **Privacy**: every value rendered in the timeline comes from the telemetry
  contract's existing metadata-only fields (`model_usage`, `error`,
  `attributes`) - e.g. a tool call's `attributes.input`/`.output` is always
  `{type, size}`, never the real value, by construction on the SDK side (M6).
  The dashboard adds no new capture of its own.

## 7. API changes

**No new backend authorization model.** Additions:

- `POST/GET /api/v1/auth/{login,me}`, `POST /api/v1/auth/logout` - new,
  narrow, independent of `AuthContext` (see section 3).
- `GET /api/v1/dashboard/overview` - new aggregate endpoint
  (`services/dashboard_service.py`), built entirely from the existing
  `tenant_scope.py` helpers (`scope_execution_list`, `scope_agent_list`,
  `scope_telemetry_event_list`), so an aggregate count and the individual
  records a caller can list always agree.
- `GET /api/v1/executions` gained three **additive, backward-compatible**
  query parameters (`environment_id`, `execution_id`, `started_after`/
  `started_before`) and an `X-Total-Count` response header for pagination -
  the response body is still a bare JSON array, unchanged, so the existing
  `response.json() == []` assertion in `tests/test_executions.py` still holds.
- Every other list/detail endpoint the dashboard uses
  (agents/environments/sessions/agent-versions/telemetry-by-execution/
  telemetry-by-trace) already existed from M4/M5 and needed no backend
  change.

## 8. Database migration instructions

```bash
# Apply:
alembic -c apps/api/alembic.ini upgrade head

# Roll back just this migration (verified to round-trip cleanly):
alembic -c apps/api/alembic.ini downgrade -1

# Check current head:
alembic -c apps/api/alembic.ini current
```

Run these from the repository root (Alembic reads `.env` relative to the
current working directory). The test database (`agentops_test`) needs no
migration step - `tests/conftest.py` creates/drops tables directly from the
SQLAlchemy metadata on every test function, so `User`/`UserSession` are
picked up automatically.

## 9. Testing instructions

```bash
# Backend (from the repository root, with apps/api[dev] installed)
pytest -q

# Frontend
cd apps/frontend
npm test              # vitest run
npm run build          # also type-checks every page
```

New backend test files: `tests/test_local_auth.py` (hashing, login,
rate-limiting, session lifecycle), `tests/test_auth_routes.py` (the HTTP
endpoints), `tests/test_dashboard.py` (the aggregate endpoint, including
tenant isolation and "unavailable vs. zero" semantics). `tests/test_executions.py`
gained new tests for the additive filters/header only - nothing existing was
changed. New frontend test files are colocated as `*.test.ts(x)` next to the
code they cover; `src/test/` holds shared test infrastructure (a `lucide-react`
resolution stub needed only under Vitest - Next.js's own bundler tolerates
the package's packaging quirk fine - and a `renderAsync` helper for pages
that call React's `use()` on their `params` prop).

The M7 follow-up (local dev mode + API key management, section 11-13) added:
`tests/test_bootstrap.py` (first-run bootstrap, idempotency, a real 5-thread
concurrency test, internal-key rotation/recovery), `tests/test_api_keys.py`
(integration-key create/list/revoke, scope enforcement, the session-or-API-key
dual-credential fallback), `src/lib/server/env.test.ts` and `session.test.ts`
(the bypass flag's own logic, including its production fail-closed guarantee),
new cases in `src/proxy.test.ts` (the same guarantee at the middleware layer),
and `src/components/settings/api-keys-section.test.tsx` (the Settings UI,
including that the raw key is rendered only immediately after creation and
never again). `src/test/server-only-stub.ts` and `set-node-env.ts` are shared
test infrastructure these needed, added the same way as the existing
`lucide-react` stub.

## 10. Known limitations

- **Login rate limiting is per-process and in-memory** (see 3.3): it resets
  on restart and does not share state across multiple `uvicorn` worker
  processes. Acceptable for this milestone's explicitly local, single-process
  scope; a distributed deployment would need a shared store (Redis, or the
  database itself) - deliberately not added now, since Redis is not
  otherwise part of this repository (see section 5's note).
- **No environment switcher** in the header: the brief allows this
  ("environment selector where applicable") and, since one API key and one
  local account currently correspond to one fixed scope, a selector would
  have nothing meaningful to switch between. The Environments page still
  lets you browse all environments in scope.
- **No "list all traces" page**: there is no backend endpoint for this (a
  trace is always one execution's own spans), so `/traces` is a landing page
  that explains this and accepts a trace ID, consistent with "do not invent
  relationships/endpoints that aren't there." Every execution's detail page
  links directly to its own trace.
- **Agent/session search is client-side, within the currently-loaded page**:
  the backend has no full-text search endpoint for agent/session names, and
  adding one was judged out of the "narrowly scoped" bar for this milestone.
  Execution search by ID *is* server-side (exact match only).
- **Single local administrator model**: `User.role` exists for future
  extensibility but every bootstrapped account is `"admin"` today - no
  permission tiers are enforced, matching the brief's exclusion of
  "multi-user invitation workflows" and "advanced organization administration."
- **`apps/frontend/env.local`** (see section 5's note) is pre-existing dead
  configuration, left untouched.
- **The local dashboard is single-user, not a multi-user authorization
  model.** With `LOCAL_AUTH_BYPASS` on, every browser session is the same
  synthetic local user, and all key-management operations run under one
  fixed, server-side internal API key scoped to one project/environment
  (section 11-12). There are no per-person permissions, invitations, or
  audit trail of "who revoked this key" beyond what the database's own
  `created_at`/`revoked_at` timestamps show. This is an explicit, documented
  limitation of the current local-dev convenience feature, not an oversight -
  a real multi-user deployment keeps auth enabled (bypass off) and relies on
  the pre-existing `User`/`UserSession` model from section 3.

## 11. Local development mode: auth bypass and automatic bootstrap

This section covers the M7 follow-up ("Additional M7 Requirements - Local
Development Mode and API Key Management"): removing the need to manually
create an admin account and an API key before seeing the dashboard, while
keeping the full M7 auth system intact and re-enablable for a real
deployment.

### 11.1 `LOCAL_AUTH_BYPASS` - the login gate, not the authorization model

`LOCAL_AUTH_BYPASS=true` in `apps/frontend/.env.local` makes
`getCurrentUser()` (`src/lib/server/session.ts`) return a fixed synthetic
user (`LOCAL_BYPASS_USER`, `src/lib/server/env.ts`) immediately, without
reading a cookie or calling the backend at all - every existing call site
(`requireUserOrRedirect`, every `/api/*` route) benefits automatically,
since this is the one function they all already funnel through. `src/proxy.ts`
carries a duplicate of the same check (it can't import `env.ts` - see the
existing note on `server-only` vs. Vitest/jsdom in section 6) so the
`/login` page itself redirects to `/` instead of rendering a form that would
never be needed.

**This changes nothing about authorization.** It only decides who
`getCurrentUser()` says is logged in; the backend's own tenant isolation
(`tenant_scope.py`, `AuthContext`) is completely unaffected and is not
even aware this flag exists - every data request this dashboard makes is
still authorized the normal M5 way, by the internal API key (section 12).

**Fail-closed, structurally, not just by convention**: the check is
`LOCAL_AUTH_BYPASS === "true" && process.env.NODE_ENV !== "production"`.
`NODE_ENV` is not an app-configurable value - Next.js itself forces it to
`"production"` for `next build`/`next start`, so there is no environment-
variable misconfiguration that enables this in a real deployment. Verified
three ways: unit tests (`env.test.ts`, `session.test.ts`, `proxy.test.ts`)
assert the bypass stays off under a forced production `NODE_ENV`; and an
actual `next build && next start` with `LOCAL_AUTH_BYPASS=true` in
`.env.local` was run end-to-end, confirming the production server still
redirects a protected page to `/login` and does not redirect `/login` away.

### 11.2 First-run bootstrap (`services/bootstrap_service.py`)

On backend startup (a FastAPI `lifespan` hook in `main.py`, gated on
`settings.app_env == "local"` and skipped under pytest via the
auto-set `PYTEST_CURRENT_TEST` env var, so the test suite never touches the
real database), `ensure_local_bootstrap()` ensures, in order, that an
organization (slug `local-default`), a project (`local-default`), a
development environment (`development`), and one active internal API key
all exist - reusing the *existing* M4/M5 org/project/environment models and
the *existing* `create_api_key`/`verify_api_key`/`revoke_api_key` services
unchanged. Nothing here is a new authorization primitive; it is the same
`ApiKey` row M5 already had, with a new `key_type` column (`"internal"` vs.
the default `"integration"`) distinguishing it from a normal SDK key.

**Idempotency and concurrency** are both enforced at the database level, not
just in application logic - a check-then-insert that merely *looks*
idempotent is racy under real concurrent startup:

- Org/project/environment already had unique `slug` constraints; a shared
  `_get_or_create()` helper retries on `IntegrityError`/`OperationalError`
  (a genuine Postgres deadlock under concurrent inserts is possible and must
  be retried, not just a uniqueness violation).
- The internal key additionally needed a **new** partial unique index,
  `uq_api_keys_one_internal_per_organization` (migration `c4d9f2a6b8e1`) -
  `UNIQUE (organization_id) WHERE key_type='internal' AND status='active'`.
  Without it, two threads racing "no internal key yet" → create both succeed,
  since `ApiKey.name` itself was never unique. This was caught by, not
  designed away from: `tests/test_bootstrap.py`'s concurrency test spawns 5
  real threads against 5 real sessions on the same test database and asserts
  exactly one of them actually created a key - it failed intermittently
  before the index was added, and is green across repeated full-suite runs
  since.
- The predicate includes `status='active'` deliberately (not just
  `key_type='internal'`): a revoked-then-replaced internal key must stop
  counting toward the constraint, or rotation (11.4) could never create its
  replacement.

### 11.3 How the internal key reaches the Next.js server

Preferred path, fully automatic: `try_write_frontend_env_local()` merges
`BACKEND_API_URL` and the newly-created raw key into
`apps/frontend/.env.local` (preserving any other lines already there), the
moment the bootstrap creates a *new* key - never on a run that found an
existing one, so restarting the backend never rewrites or regenerates
anything. The raw value is **never logged**; only the key's id appears in
the one log line confirming a key was created. `.env.local` was already
gitignored before this phase (see section 5).

If that write fails (e.g. a read-only filesystem, or `apps/frontend` not
present next to `apps/api` in this checkout) it's caught, logged as a
warning with no secret in it, and the documented fallback - a one-time CLI
command - takes over; automatic provisioning degrading to a manual step is
an explicit, acceptable fallback per the brief, not a silent failure.

### 11.4 Recovery and rotation (`apps/api/scripts/bootstrap_local_dev.py`)

```bash
# Re-run the idempotent bootstrap and (re-)write .env.local - safe to run
# any time, including if .env.local was deleted or you're missing it after
# cloning onto a machine that already has the database:
python apps/api/scripts/bootstrap_local_dev.py --backend-url http://localhost:8010

# Revoke the current internal key and mint + provision a fresh one (the
# correct way to rotate - there is no "regenerate from an old secret"):
python apps/api/scripts/bootstrap_local_dev.py --rotate

# Print the raw key once instead of writing .env.local (e.g. to paste into
# a different tool's config by hand); it is never logged otherwise:
python apps/api/scripts/bootstrap_local_dev.py --print-key
```

`--rotate` calls `rotate_internal_key()`, which revokes the existing
internal key via the *existing, unmodified* `revoke_api_key()` and only then
creates a replacement - the same revoke-then-create-new process the API key
management UI uses for integration keys (section 12), kept consistent on
purpose.

## 12. API key management

### 12.1 Internal vs. integration keys

Both are `ApiKey` rows using the same M5 table, generation, hashing
(SHA-256 of a high-entropy token - see section 3.2's justification, which
applies equally here), and verification/revocation code. The only new thing
is `key_type`:

| | `internal` | `integration` (default) |
|---|---|---|
| Created by | The backend's own bootstrap/rotation (11.2-11.4) | A platform user, via Settings → API Keys |
| Used by | This app's Next.js server only, to call its own backend | The Python SDK / external agents |
| Visible in the Settings UI? | **Never** - excluded by `key_type="integration"` filters in every list/revoke query | Yes |
| Scope | One fixed project/environment (the bootstrap's own) | Chosen at creation (org-wide, or narrowed to a project/environment the caller's scope actually owns) |

An internal key can never be listed or revoked through the integration-key
endpoints (`GET/POST /api/v1/auth/api-keys`, `POST .../revoke` -
`routers/auth.py`): each query is always filtered to
`key_type="integration"`, and the revoke lookup additionally 404s (not 403 -
indistinguishable from "doesn't exist") on any key that isn't both
integration-typed and in the caller's own organization.

### 12.2 Authorizing key-management requests under the bypass

The Settings page's API-key endpoints need *some* credential even when
`LOCAL_AUTH_BYPASS` means there's no real login session. Rather than teach
the backend anything about the frontend's bypass concept, `auth.py`'s
`get_key_management_scope` dependency accepts **either**: a valid
`X-Session-Token` (checked first), **or** falls back to the same tenant-API-
key `AuthContext` the SDK itself uses (`Authorization: Bearer ...`). The
frontend's `keyManagementRequest()` helper sends a session token when one
exists and the internal API key otherwise - so this works identically
whether a real person is logged in or the bypass is active, with no special
casing either side needs to know about.

> **Operational note verified live**: if a real session cookie set on
> `localhost` by an earlier *login* ever outlives the tab that created it,
> it is still sent on any `localhost` port, bypass or not - cookies aren't
> port-scoped. Because session tokens are checked first by design (future
> multi-user support should prefer a real session over a shared key), that
> stale session - not the internal key - determines the key-management
> scope until it's logged out or expires. This surfaced during this
> feature's own live verification and is working as designed, not a bug;
> worth knowing if Settings ever appears to show the "wrong" organization's
> keys in a long-lived local browser profile.

### 12.3 The Settings UI (`src/components/settings/api-keys-section.tsx`)

List, create (name only - project/environment scope defaults to the
caller's own, and a browser-supplied `organization_id` is rejected outright
by the schema's `extra="forbid"`), and revoke (behind an inline "Revoke this
key? Confirm/Cancel" step - no destructive action fires on the first click).
The raw key is shown exactly once, immediately after creation, in a
dismissible callout with a copy button and an explicit "cannot be shown
again" notice; closing it or reloading the page cannot bring it back,
because the raw value was never persisted anywhere to begin with (section
3.2/12.1's hashing is unchanged) - the UI has nothing to re-fetch.
Regeneration from an old key is not a feature that exists: revoke, then
create a new one, same as 11.4's own rotation path.

## 13. Python SDK onboarding

Immediately after creating an integration key, the Settings UI shows (via
`src/components/settings/sdk-onboarding-guide.tsx`, collapsed by default
under "How do I use this with the Python SDK?"): the install command
(`pip install agentops-sdk-python`), exporting `AGENTOPS_API_KEY` /
`AGENTOPS_ENDPOINT` as environment variables, and a minimal example using
the SDK's actual M6 public API - `AgentOps(endpoint=..., api_key=...)`,
`.agent(id, version=...)`, `.start_execution(agent=..., session_id=...)`,
and the `llm_call`/`tool_call` telemetry context managers - ending with a
pointer to the SDK's own README for async usage and its full
privacy/security model. The example always uses a placeholder
(`"<the key you just copied above>"`); the real key is never written into
documentation or example code, only ever shown once in the callout above it.

## 14. Security and deployment boundaries (updated)

Restating section 3's boundary with this phase's additions:

- The local-auth bypass (11.1) only ever decides who the *frontend* thinks
  is logged in. It cannot widen, and was not designed to interact with, the
  backend's own tenant isolation - that boundary is exactly as it was after
  M5, re-confirmed by re-running the full pre-existing test suite (section
  9) alongside this phase's new tests.
- The bypass is refused outside local development by construction
  (`NODE_ENV`), not by a flag the operator has to remember to unset - see
  11.1 for how this was verified end-to-end, not just unit-tested.
- The internal key never leaves the server: it is read only in
  `src/lib/server/proxy.ts`/`backend.ts` (both `server-only`-guarded, same
  mechanism as the pre-existing `AGENTOPS_API_KEY` in section 4.4), never
  rendered in any page, and never returned by any API route - the Settings
  UI's key list always filters it out at the database query level (12.1),
  not just in the UI layer, so there is no endpoint that could leak it even
  if the frontend had a bug.
- The Python SDK's own authentication is completely unchanged: normal
  `Authorization: Bearer <integration key>`, verified by the same
  `get_auth_context`/`AuthContext` dependency it always used.
- See section 10's new bullet: the local-auth-bypass mode itself remains a
  single-user local convenience layer. Section 15 below covers the separate,
  now-multi-tenant self-service signup path, which supersedes that
  limitation for the normal (bypass-off) case.

## 15. Self-service customer onboarding (M8)

This section covers the M8 milestone: replacing the fixed single
"Local Organization" experience with real, customer-created organizations -
signup, project, environment, and integration key, each a genuinely new
tenant rather than a shared local default - while keeping M1-M7's tenant
isolation and the M7-follow-up's local-dev conveniences (sections 1-14)
fully intact and unaffected.

### 15.1 The one architectural change: `AuthContext` also accepts a session

Every resource router (agents, executions, sessions, environments,
telemetry, dashboard) already depended on `get_auth_context` returning an
`AuthContext` (organization/project/environment id) built from a verified
API key (section 3.1). `agentops_api/auth.py`'s `get_auth_context` now
*also* accepts an `X-Session-Token` header, tried first: when it resolves
to a valid `UserSession`, `AuthContext` is built from that session's own
`User.organization_id`/`project_id` instead (`api_key_id` is `None` in
this case - the one field only ever used for the API-key-only
`last_used_at` bookkeeping). This mirrors the M7-follow-up's
`get_key_management_scope` (section 12.2), generalized to every resource
endpoint rather than only API-key management.

**This is a pure addition, not a rewrite.** `tenant_scope.py` and every
resource service (`environment_service.create_environment`,
`agent_service.create_agent`, etc.) already took `AuthContext` and only
ever read its three tenant-id fields - none of them changed at all. A
signed-up customer's own dashboard session now flows through literally the
same scoping code the SDK's API keys always used; the only new code is
*how* `AuthContext` gets constructed. The SDK itself, and every existing
API-key caller, is entirely unaffected - they never send a session token,
so this new branch never activates for them (confirmed by the existing
356+-test regression suite passing unchanged, plus the dual-credential
priority tests in `tests/test_signup.py` and `tests/test_api_keys.py`).

### 15.2 Signup (`POST /api/v1/auth/signup`, `services/auth_service.signup`)

Creates a brand-new `Organization` (via the new
`services/organization_service.create_organization`, which auto-derives a
URL-safe slug from the customer's free-text organization name, retrying
with a random suffix only on a collision - a customer is never asked to
invent a slug) and its first `User` (role `admin`) in one transaction,
then immediately logs them in (`create_session`, the same call `/login`
makes) - a first-time customer lands on the onboarding wizard with no
separate login step. A duplicate email is rejected (409) before the
organization is even inserted, so a rejected signup never leaves an
orphaned, user-less organization behind (`tests/test_signup.py`).

`UserResponse` (returned by signup, login and `/me`) now also carries
`organization_name`/`project_name`, read via the existing
`User.organization`/`User.project` relationships (`UserResponse.from_user`)
- purely a display convenience: the dashboard's sidebar and Settings page
now show the customer's own organization name instead of the old hardcoded
"Local organization" string, and still never use these for authorization.

### 15.3 Project creation (`POST /api/v1/projects`, `services/organization_service.create_project`)

The one other genuinely new write. Scoped entirely by the caller's own
`AuthContext.organization_id` - never a request body field - exactly like
`environment_service.create_environment` already was; rejected if the
caller's identity is already narrowed to one project/environment, the same
check `create_environment` makes. Slugs are auto-derived the same way
organizations' are.

### 15.4 Environment and integration-key creation: zero new code

`POST /api/v1/environments` (M4) and the integration-key endpoints (M7
follow-up, section 12) needed **no changes at all** - once a logged-in
customer's session resolves to their own `AuthContext` (15.1), these
pre-existing, already-tested endpoints work for them automatically. The
onboarding wizard (`src/components/onboarding/onboarding-wizard.tsx`) is a
three-step client-side flow - create project, create environment, then the
*existing* `ApiKeysSection`/`SdkOnboardingGuide` components (section
12.3/13), embedded unchanged - backed by two new Next.js routes
(`/api/projects`, and a `POST` added to the existing `/api/environments`
route) that both go through `src/lib/server/proxy.ts`'s new `proxyMutate`
helper: session-gated, CSRF-checked, forwarded via `backendRequest`.

### 15.5 How the dashboard's own backend calls became per-customer

`src/lib/server/backend.ts`'s `backendRequest` - the single function every
proxied `/api/*` route handler already went through - now sends the
caller's own dashboard session token (`X-Session-Token`) when one exists,
falling back to this deployment's internal API key only when there is none
(the local-auth-bypass case, section 11). This is the frontend half of
15.1: it is what makes a signed-up customer's *browser* session - not just
direct API calls - see only their own organization's agents, executions,
traces and telemetry. `keyManagementRequest` (section 12.2) was simplified
to call the same `backendRequest`, removing what had been its own
duplicate copy of this credential-selection logic.

### 15.6 Validated tenant isolation (two independent customers)

`tests/test_signup.py::test_two_separately_signed_up_customers_have_fully_isolated_dashboards`
signs up two customers end-to-end (organization, project, environment,
integration key), registers one agent each via their own key, and asserts
each customer's own **session** (the dashboard's actual code path, not
just their API key) sees only their own agent in `GET /api/v1/agents`,
only their own count in `GET /api/v1/dashboard/overview`, and only their
own key in `GET /api/v1/auth/api-keys`.

This was additionally verified live, end-to-end, through the real browser
UI and the real `agentops_sdk` package (not mocked): two customers signed
up through `/signup`, each completed the onboarding wizard, each key was
used to register a real agent and send a real execution plus `llm_call`/
`tool_call` telemetry through the SDK exactly as section 13 documents it,
and each customer's own dashboard (Agents, Overview, Settings -> API Keys)
was confirmed to show only their own data - including one incidental,
expected observation: a stale session cookie from an earlier customer's
login, if not explicitly logged out, would continue to resolve to *that*
customer under `AuthContext`'s session-first priority (the same behavior
already documented for key management in section 12.2) - ordinary browser
cookie behavior, not a tenant-isolation gap, and the login/logout flow
already clears it.

### 15.7 What is still out of scope

No invitation flow (a second person joining an existing organization),
no role/permission tiers beyond the single `admin` every signup creates
(same limitation as section 10's pre-existing bullet), no "create an
additional organization" affordance for an already-logged-in user, and no
self-service password reset. None of these were asked for by the M8 brief,
which scopes the customer journey to exactly: signup, organization,
project, environment, integration key, SDK connection, telemetry, and
dashboard visibility.
