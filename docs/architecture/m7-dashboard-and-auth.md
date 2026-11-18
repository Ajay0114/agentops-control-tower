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
cp .env.example .env.local   # fill in AGENTOPS_API_KEY - see section 5
npm run dev                  # http://localhost:3000
```

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
| `AGENTOPS_API_KEY` | Yes | A tenant-scoped API key provisioned via `provision_api_key.py create-key` (see section 2, step 3). **Never** exposed to the browser - read only from `src/lib/server/env.ts`, which is `server-only`-guarded. |

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
