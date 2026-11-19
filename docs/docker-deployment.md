# Running and hosting AgentOps Control Tower with Docker

This covers the `Dockerfile`s for the backend (`apps/api`) and frontend
(`apps/frontend`), and the `docker-compose.yml` extension that runs the
whole stack - Postgres, the FastAPI backend, and the Next.js frontend -
together. It assumes familiarity with `docs/architecture/
m7-dashboard-and-auth.md`, particularly its sections on the local-auth
bypass (11) and self-service customer onboarding (15).

## 1. Running it locally

```bash
cp .env.example .env   # fill in POSTGRES_PASSWORD at least
docker compose up --build
```

This builds and starts three containers:

| Service | Image | Port | Depends on |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` (unchanged from before) | 5434 | - |
| `api` | built from `apps/api/Dockerfile` | 8010 | `postgres` (healthy) |
| `frontend` | built from `apps/frontend/Dockerfile` | 3000 | `api` |

Open `http://localhost:3000` and sign up through `/signup` - the same
self-service flow documented in architecture section 15. There is no
admin account to create or API key to provision by hand first; a
container restart is also safe (`alembic upgrade head` in the API's
entrypoint is a no-op once the schema is current).

## 2. What changed to make this work

- **`apps/api/Dockerfile`**: installs the backend as a normal (non-editable)
  package from `pyproject.toml`'s base dependencies only - no `[dev]`
  extras (pytest/ruff/httpx) in the runtime image - then runs
  `alembic upgrade head && uvicorn ...` on every start.
- **`apps/frontend/Dockerfile`**: a three-stage build (`deps` → `builder` →
  `runner`) using Next.js's `output: "standalone"` (added to
  `next.config.ts` for this), so the final image ships only the
  node_modules this app actually needs, not a full `npm install`.
  `HOSTNAME=0.0.0.0` is set explicitly - the standalone server binds to
  `localhost` otherwise, which Docker's port mapping can't reach.
- **`docker-compose.yml`**: the new `api` service sets `APP_ENV=docker`
  (anything other than `"local"`) specifically so `main.py`'s local-only
  bootstrap hook - which tries to write a key into
  `apps/frontend/.env.local` on the *host* filesystem - never runs inside
  a container, where that path doesn't exist and wouldn't mean anything if
  it did. The new `frontend` service points `BACKEND_API_URL` at the `api`
  service by its Compose network name (`http://api:8010`) and leaves
  `LOCAL_AUTH_BYPASS` off.

## 3. Why no `AGENTOPS_API_KEY` is needed here

In the normal multi-tenant flow (bypass off), the frontend never actually
calls `getBackendApiKey()`: every proxied request first confirms a logged-in
user (`getCurrentUser()`), and by that point either the bypass is active
(not the case here) or a real session cookie already exists - which
`backendRequest` (`lib/server/backend.ts`) then sends as `X-Session-Token`
instead of ever falling back to the internal key. `AGENTOPS_API_KEY` is
only consulted if you explicitly set `LOCAL_AUTH_BYPASS=true` on the
`frontend` service (see `.env.example`'s comment) - a convenience for a
single-operator deployment, not something a real multi-customer deployment
needs.

## 4. Hosting it somewhere

This compose file is enough to run the whole stack on any machine with
Docker - a plain VPS (`docker compose up -d` over SSH is enough), or an
open-source self-hosted PaaS built on Docker Compose, such as
[Coolify](https://coolify.io) or [Dokku](https://dokku.com), which add a
web UI, git-push deploys, and automatic HTTPS on top of the same
`docker-compose.yml`. Either way, put a reverse proxy (Caddy, Traefik, or
whatever the PaaS provides) in front of ports 3000/8010 for real TLS, and
set `LOCAL_AUTH_BYPASS` to `false`/unset in that environment - the bypass
is already refused in any `next build`/`next start` deployment regardless
(section 11.1), but the compose file leaves it unset by default too, for
clarity.

## 5. Known limitation

The frontend's `HEALTHCHECK` hits `/login`, which the proxy's own
protected-route gate always serves regardless of auth state, so it only
proves the Node process is up - it does not check that it can actually
reach the `api` service. `docker compose ps` combined with the API's own
`/health/ready` (which does check its database connection) covers that.
