# AgentOps Control Tower — Dashboard

The web dashboard for AgentOps Control Tower: local login, and
observability into registered agents, executions, sessions and traces,
backed by the real FastAPI/PostgreSQL backend in `apps/api`.

## Setup

Requires Node.js **20.9+** (Next.js 16 does not support Node 18) and a
running backend (see the repository root). From this directory:

```bash
npm install
cp .env.example .env.local
# edit .env.local: set AGENTOPS_API_KEY to a key provisioned with
# apps/api/scripts/provision_api_key.py create-key (see
# docs/architecture/m7-dashboard-and-auth.md, sections 2 and 5)
npm run dev
```

Then sign in at [http://localhost:3000/login](http://localhost:3000/login)
with a local administrator account - bootstrap one first with
`apps/api/scripts/bootstrap_admin.py` if you haven't already (see the same
doc, section 2).

> Running inside WSL2 against a repository mounted from Windows
> (`/mnt/c/...`, `/mnt/d/...`)? `next dev`/`next build` can crash with `Bus
> error` - a Turbopack/drvfs incompatibility, not a code issue. Work from a
> native Linux path (e.g. `~/agentops-control-tower`) instead, or run Node
> natively on Windows.

## Testing

```bash
npm test         # vitest run
npm run build     # also type-checks every page
```

## Architecture

See [`docs/architecture/m7-dashboard-and-auth.md`](../../docs/architecture/m7-dashboard-and-auth.md)
at the repository root for the full write-up: the local-auth model, the
browser → Next.js → FastAPI trust boundary (the browser never talks to
FastAPI directly, and never holds any backend credential), CSRF, and the
dashboard's own structure (`src/app/(dashboard)/`, the centralized API
client in `src/lib/api/client.ts`, and the server-only backend proxy in
`src/lib/server/`).
