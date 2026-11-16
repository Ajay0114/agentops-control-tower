# Milestone 1 --- Project Foundation

**Project:** AgentOps Control Tower\
**Milestone:** 1 --- Repository, local development environment, database
foundation, and API skeleton\
**Status:** Completed and verified\
**Initial commit:** `f3f7196` ---
`chore: initialize AgentOps Control Tower`

------------------------------------------------------------------------

## 1. Purpose and scope

Milestone 1 established the engineering foundation on which AgentOps
Control Tower will be built. The objective was not to implement agent
monitoring yet. It was to create a reproducible local development
environment, establish the backend application structure, run
PostgreSQL, introduce database migrations, and verify that the API can
connect to the database.

At completion, the project had:

-   A Git repository with a `main` branch and a successful initial
    GitHub push.
-   A Python 3.12 virtual environment and installable backend package.
-   A Docker Compose-managed PostgreSQL database.
-   A FastAPI application.
-   SQLAlchemy database connectivity and an initial ORM model layer.
-   Alembic migration infrastructure.
-   Two initial database entities: organizations and projects.
-   Root, liveness, and readiness HTTP endpoints.

**Boundary:** Agent registry, agent versions, environments, executions,
traces, spans, telemetry ingestion, evaluation, incidents, and
dashboards are not implemented in Milestone 1. They are planned for
later milestones.

## 2. Technology choices and responsibilities

  -----------------------------------------------------------------------
  Technology                          Responsibility in Milestone 1
  ----------------------------------- -----------------------------------
  Python 3.12                         Backend runtime

  FastAPI                             HTTP API framework

  Uvicorn                             ASGI server used to run the API
                                      locally

  SQLAlchemy 2.x                      ORM and database access

  PostgreSQL 16                       Relational database

  psycopg 3                           PostgreSQL driver

  Alembic                             Version-controlled database schema
                                      migrations

  Pydantic Settings                   Application configuration from
                                      environment variables

  Docker Compose                      Local PostgreSQL lifecycle

  Git                                 Source control

  GitHub                              Remote repository and source backup

  pytest / HTTPX                      Test dependencies configured for
                                      later use

  Ruff                                Python linting and formatting tool
                                      configured for later use
  -----------------------------------------------------------------------

### Why this stack?

-   **FastAPI** provides typed request handling, OpenAPI documentation,
    dependency injection, and asynchronous endpoint support.
-   **PostgreSQL** is a reliable relational foundation for tenant,
    project, agent, execution, and telemetry metadata.
-   **SQLAlchemy** separates database models and queries from HTTP route
    handlers.
-   **Alembic** records schema changes as migrations, so a database can
    be recreated or upgraded consistently.
-   **Docker Compose** avoids requiring a separately installed
    PostgreSQL server on the developer machine.
-   **Pydantic Settings** centralizes configuration and keeps
    environment-specific values out of source code.

## 3. Repository layout

The repository is organized as a modular monorepo. The directories for
future services and integrations are structural placeholders at this
stage; they do not all contain implemented applications.

``` text
agentops-control-tower/
├── apps/
│   ├── frontend/                  # Reserved for Next.js frontend
│   └── api/
│       ├── src/
│       │   └── agentops_api/
│       │       ├── models/
│       │       │   ├── __init__.py
│       │       │   ├── base.py
│       │       │   └── core.py
│       │       ├── __init__.py
│       │       ├── config.py
│       │       ├── db.py
│       │       └── main.py
│       ├── migrations/
│       │   ├── versions/
│       │   │   └── 0001_platform_foundation.py
│       │   ├── env.py
│       ├── pyproject.toml
│       └── alembic.ini
├── services/
│   ├── ingestion-worker/
│   ├── evaluation-engine/
│   ├── incident-engine/
│   └── intelligence-engine/
├── packages/
│   ├── telemetry-contracts/
│   ├── shared-types/
│   └── agentops-sdk-python/
├── integrations/
│   ├── custom-python/
│   ├── langgraph/
│   ├── kore-xo/
│   └── kore-artemis/
├── examples/
│   ├── customer-support-agent/
│   └── multi-agent-workflow/
├── infrastructure/
│   ├── docker/
│   ├── otel-collector/
│   ├── terraform/
│   └── kubernetes/
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── database/
│   └── prd/
├── tests/
│   ├── integration/
│   ├── performance/
│   └── security/
├── docker-compose.yml
├── .env
├── .env.example
├── .gitignore
└── README.md
```

### Why a monorepo?

A monorepo keeps the API, SDK, integrations, frontend, services,
infrastructure, and documentation under one version-controlled project.
It makes it easier to evolve shared telemetry contracts and coordinate
changes across components.

The directory structure is an architectural starting point, not a claim
that every listed component is already implemented.

## 4. Execution hierarchy --- how the system runs

``` text
Developer / Terminal
│
├── 1. Activate Python virtual environment
│      └── .venv
│
├── 2. Start infrastructure
│      └── Docker Compose
│           └── PostgreSQL container
│                └── Persistent Docker volume
│
├── 3. Configure backend
│      ├── .env
│      └── Pydantic Settings
│
├── 4. Database initialization / schema management
│      └── Alembic
│           ├── migrations/env.py
│           └── migrations/versions/
│                └── 0001_platform_foundation.py
│
└── 5. Start API
       └── Uvicorn
            └── FastAPI application
                 ├── GET /
                 ├── GET /health/live
                 ├── GET /health/ready
                 ├── Configuration
                 ├── SQLAlchemy engine
                 └── PostgreSQL
```

### Runtime request path

For a database-dependent request such as `GET /health/ready`:

1.  A client sends an HTTP request to Uvicorn's listening address.
2.  Uvicorn forwards the ASGI request to the FastAPI application.
3.  FastAPI matches the request to the readiness endpoint.
4.  The endpoint obtains a SQLAlchemy database connection.
5.  SQLAlchemy uses the configured PostgreSQL URL and the psycopg
    driver.
6.  PostgreSQL executes a lightweight `SELECT 1`.
7.  The result returns through SQLAlchemy and FastAPI.
8.  FastAPI returns an HTTP response to the client.

This is a synchronous database health check in the current
implementation. It is separate from the future asynchronous telemetry
ingestion architecture.

**Important distinction:** Uvicorn runs the API server; FastAPI handles
HTTP requests; SQLAlchemy handles database connectivity and ORM
operations; PostgreSQL stores records; Alembic manages schema versions.
Alembic is used during setup/deployment or schema upgrades, not on every
HTTP request.

## 5. Step-by-step implementation

### Step 1 --- Prepare the development environment

The project was developed in WSL using Ubuntu.

  Component        Verified version
  ---------------- ------------------
  Ubuntu           24.04.3 LTS
  Python           3.12.3
  Node.js          22.23.4
  Git              2.43.0
  Docker           29.4.3
  Docker Compose   5.1.3

Useful checks:

``` bash
python3 --version
git --version
docker --version
docker compose version
```

Node.js is available for the future Next.js frontend; the backend
milestone primarily uses Python.

### Step 2 --- Enter the repository

Project directory:

``` bash
cd /mnt/d/Agents/agentops-control-tower
```

The repository was initialized with Git and the project directory
structure was created.

### Step 3 --- Create the Python virtual environment

A virtual environment isolates this project's Python dependencies from
the operating system and other projects.

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

After activation, the terminal prompt displays `(.venv)`.

Install the backend package and development dependencies:

``` bash
python -m pip install --upgrade pip
python -m pip install -e "apps/api[dev]"
```

The `-e` flag installs the backend in editable mode. Changes to the
source package are available without reinstalling the project each time.
The `[dev]` extra installs the test and linting tools declared in
`pyproject.toml`.

### Step 4 --- Define the backend package

Backend source location:

`apps/api/src/agentops_api/`

The source-layout convention separates application source code from
project configuration and migration files.

Package metadata and dependencies are declared in
`apps/api/pyproject.toml`.

Key configuration:

-   Package name: `agentops-api`
-   Version: `0.1.0`
-   Python requirement: `>=3.12`
-   Build backend: setuptools
-   Source package directory: `src`
-   Test directory: `tests`
-   Ruff target: Python 3.12
-   Ruff line length: 100

### Step 5 --- Configure environment variables

Two configuration files are used:

-   `.env.example`: safe template committed to Git.
-   `.env`: local configuration containing the actual development
    credentials; it must remain untracked.

The example configuration:

``` env
POSTGRES_USER=agentops
POSTGRES_PASSWORD=replace_with_a_local_password
POSTGRES_DB=agentops

DATABASE_URL=postgresql+psycopg://agentops:replace_with_a_local_password@localhost:5434/agentops

APP_NAME=AgentOps Control Tower API
APP_ENV=local
```

The real `.env` was created from the example and populated with a
generated local database password. The same password must be used in
both `POSTGRES_PASSWORD` and the password portion of `DATABASE_URL`.

**Security:** Never copy the actual `.env` contents into documentation,
source control, screenshots, or chat. If a real credential is
accidentally committed or exposed, removing the file in a later commit
is not sufficient; rotate the credential.

### Step 6 --- Configure Docker Compose and PostgreSQL

The root `docker-compose.yml` defines the PostgreSQL service.

Its responsibilities:

-   Pull and run the PostgreSQL 16 Alpine image.
-   Create the database using environment variables.
-   Publish the container's PostgreSQL port to the host.
-   Persist database files in a named Docker volume.
-   Run a health check using `pg_isready`.

Verified configuration:

-   Host: `localhost:5434`
-   Container port: `5432`
-   Container name: `agentops-postgres`
-   Database: `agentops`
-   Named volume: `agentops_postgres_data`

Start PostgreSQL:

``` bash
docker compose up -d
```

Check its state:

``` bash
docker compose ps
```

Expected: the `agentops-postgres` container is `Up` and its health
status is `healthy`.

Stop the service without deleting its data:

``` bash
docker compose down
```

Do not use `docker compose down -v` unless you intentionally want to
remove the named database volume and its data.

**Network security note:** the earlier verification output showed
PostgreSQL published on `0.0.0.0:5434`. For a local-only development
database, prefer binding the host port to loopback, for example
`127.0.0.1:5434:5432`, then recreate the service. Do not expose a
development database publicly.

### Step 7 --- Implement application settings

File: `apps/api/src/agentops_api/config.py`

This module defines a Pydantic Settings class.

Responsibilities:

1.  Read configuration from environment variables and the local `.env`
    file.
2.  Validate and expose typed settings.
3.  Ignore unrelated extra environment entries.
4.  Provide a cached `get_settings()` accessor.

The application name, environment, and database URL are not hard-coded
in route handlers. This makes the application configurable for local,
test, staging, and production environments.

### Step 8 --- Implement database connectivity

File: `apps/api/src/agentops_api/db.py`

This module creates the SQLAlchemy engine and session factory.

``` text
Application code
    │
    ▼
SessionLocal
    │
    ▼
SQLAlchemy Engine
    │
    ▼
psycopg PostgreSQL driver
    │
    ▼
PostgreSQL database
```

Key concepts:

-   **Engine:** manages database connectivity and connection pooling.
-   **Session:** represents a unit of work for database operations.
-   **SessionLocal:** factory used to create sessions.
-   **get_db:** FastAPI dependency that yields a session to a request
    and closes it when the request finishes.
-   **pool_pre_ping:** checks pooled connections before use to reduce
    failures caused by stale connections.

The current implementation uses SQLAlchemy's synchronous engine and
session model. A future change to async database access should be made
deliberately, not assumed.

### Step 9 --- Create the initial ORM model foundation

Files:

-   `apps/api/src/agentops_api/models/base.py`
-   `apps/api/src/agentops_api/models/core.py`
-   `apps/api/src/agentops_api/models/__init__.py`

#### Declarative Base

`base.py` defines SQLAlchemy's `DeclarativeBase` and a consistent naming
convention for database constraints and indexes. A shared Base lets
Alembic inspect model metadata and understand the application's tables.

#### Organization model

The `Organization` model represents a tenant or customer organization.

-   `id`: UUID primary key.
-   `name`: organization display name.
-   `slug`: unique machine-friendly identifier.
-   `created_at`: creation timestamp.
-   `projects`: ORM relationship to projects.

#### Project model

The `Project` model groups work within an organization.

-   `id`: UUID primary key.
-   `organization_id`: foreign key to the owning organization.
-   `name`: project display name.
-   `slug`: project identifier unique within its organization.
-   `created_at`: creation timestamp.
-   `organization`: ORM relationship back to the organization.

The database enforces uniqueness of `(organization_id, slug)`. This
allows two different organizations to use the same project slug without
collision.

#### Relationship

``` text
Organization
   │
   │ one-to-many
   ▼
Project
```

An organization can own multiple projects. Each project belongs to one
organization.

This is the first step toward tenant-aware data ownership. It is **not
yet complete production tenant isolation**. Later milestones must apply
tenant scoping consistently to queries, APIs, credentials, background
jobs, and database constraints.

### Step 10 --- Configure Alembic migrations

Files:

-   `apps/api/alembic.ini`
-   `apps/api/migrations/env.py`
-   `apps/api/migrations/versions/0001_platform_foundation.py`

Alembic manages database schema changes over time.

  ---------------------------------------------------------------------------------------
  File                                                Responsibility
  --------------------------------------------------- -----------------------------------
  `alembic.ini`                                       Alembic configuration and migration
                                                      script location

  `migrations/env.py`                                 Loads application settings and
                                                      model metadata; configures
                                                      migration execution

  `migrations/versions/0001_platform_foundation.py`   Creates the initial organization
                                                      and project schema
  ---------------------------------------------------------------------------------------

The migration environment imports the model metadata so Alembic can
understand the application's tables. The database URL is obtained from
application settings rather than relying on a real password committed in
`alembic.ini`.

Migration flow:

``` text
SQLAlchemy models
       │
       ▼
Base.metadata
       │
       ▼
Alembic migration environment
       │
       ▼
Migration revision
       │
       ▼
PostgreSQL schema
```

The first migration creates:

-   `organizations`
-   `projects`
-   Primary keys
-   Foreign key from projects to organizations
-   Unique constraints
-   Organization lookup index

Apply migrations:

``` bash
alembic -c apps/api/alembic.ini upgrade head
```

Check the currently applied revision:

``` bash
alembic -c apps/api/alembic.ini current
```

Verified result: `0001_platform_foundation (head)`.

**Important:** editing an existing migration after it has been applied
is not the normal way to evolve a shared database. Create a new
migration for subsequent schema changes.

### Step 11 --- Implement the FastAPI application

File: `apps/api/src/agentops_api/main.py`

This module creates the FastAPI application and defines the initial HTTP
endpoints.

#### Root endpoint --- `GET /`

Returns basic application information, including application name,
environment, version, and running status.

Purpose: a simple endpoint to verify that the API process is responding.

#### Liveness endpoint --- `GET /health/live`

Returns:

``` json
{
  "status": "alive"
}
```

Purpose: indicates that the application process is alive and can respond
to HTTP requests. It does not prove that PostgreSQL or other
dependencies are available.

#### Readiness endpoint --- `GET /health/ready`

The endpoint executes a lightweight database query, `SELECT 1`.

Successful response:

``` json
{
  "status": "ready",
  "dependencies": {
    "database": "connected"
  }
}
```

If the database check fails, the endpoint returns an HTTP 503 response.

Purpose: indicates whether the API is ready to serve requests that
depend on the database.

### Step 12 --- Run the API locally

With the virtual environment active and dependencies installed:

``` bash
uvicorn agentops_api.main:app --reload --host 127.0.0.1 --port 8010
```

Explanation:

-   `uvicorn`: starts the ASGI server.
-   `agentops_api.main`: imports the `main.py` module from the package.
-   `:app`: selects the FastAPI object named `app`.
-   `--reload`: restarts the development server when source files
    change.
-   `--host 127.0.0.1`: binds the API to the local machine.
-   `--port 8010`: serves the API on port 8010.

The API was verified at `http://127.0.0.1:8010`.

Interactive API documentation is available at
`http://127.0.0.1:8010/docs`.

The reload option is for development, not production deployment.

## 6. End-to-end startup sequence

For a fresh terminal session, use this order.

### Terminal 1 --- Start PostgreSQL

``` bash
cd /mnt/d/Agents/agentops-control-tower
docker compose up -d
docker compose ps
```

Wait until PostgreSQL reports healthy.

### Terminal 2 --- Activate the backend and apply migrations

``` bash
cd /mnt/d/Agents/agentops-control-tower
source .venv/bin/activate
python -m pip install -e "apps/api[dev]"
alembic -c apps/api/alembic.ini upgrade head
alembic -c apps/api/alembic.ini current
```

### Terminal 2 --- Start the API

``` bash
uvicorn agentops_api.main:app --reload --host 127.0.0.1 --port 8010
```

### Terminal 3 --- Verify the endpoints

``` bash
curl -i http://127.0.0.1:8010/
curl -i http://127.0.0.1:8010/health/live
curl -i http://127.0.0.1:8010/health/ready
```

## 7. Database verification performed

A direct database verification script was executed successfully. It
inserted and queried an organization and a project.

  Entity            Value
  ----------------- ----------------------------------------
  Organization      AgentOps Demo Organization
  Organization ID   `e2249579-b320-4144-a396-74cf81fd699a`
  Project           AgentOps Development
  Project ID        `7d6a0db5-1d47-41e9-a8b7-afcd85348a63`

This confirms that:

1.  PostgreSQL was running.
2.  The database and credentials were usable.
3.  SQLAlchemy could establish a connection.
4.  The initial schema existed.
5.  The organization record could be inserted and read.
6.  The project record could be inserted and read.
7.  The organization-project relationship was usable.

These are development verification records, not production customer
data.

## 8. Verification results and acceptance criteria

  -------------------------------------------------------------------------------------------------------
  Check                   Command / method                            Verified result
  ----------------------- ------------------------------------------- -----------------------------------
  PostgreSQL container    `docker compose ps`                         Up and healthy

  Database migration      `alembic -c apps/api/alembic.ini current`   `0001_platform_foundation (head)`

  Root API                `curl http://127.0.0.1:8010/`               Running response

  Liveness                `curl http://127.0.0.1:8010/health/live`    `alive`

  Readiness               `curl http://127.0.0.1:8010/health/ready`   `ready`, database connected

  ORM insert/read         Direct SQLAlchemy verification              Organization and project
                                                                      successfully inserted and queried

  Git commit              `git log -1 --oneline`                      `f3f7196` initial commit

  GitHub push             `git push`                                  `main` pushed successfully
  -------------------------------------------------------------------------------------------------------

### Liveness versus readiness

-   **Liveness:** Should the process be restarted because the
    application is not functioning?
-   **Readiness:** Should this instance receive traffic because its
    required dependencies are available?

A process can be alive but not ready. For example, the API can still
respond to the liveness endpoint while PostgreSQL is unavailable.

## 9. Git and GitHub workflow

The repository was initialized on the `main` branch. Git identity was
configured locally for the repository, then the initial files were
committed and pushed.

``` bash
git add .
git commit -m "chore: initialize AgentOps Control Tower"
git push -u origin main
```

Successful initial commit:

`f3f7196 chore: initialize AgentOps Control Tower`

Remote repository:

https://github.com/AjaykumarKothapally/agentops-control-tower

### Secret and generated-file protection

The `.gitignore` excludes the local virtual environment and environment
files while allowing the safe example template to be committed.

Useful checks:

``` bash
git status
git ls-files .env
git check-ignore .env
git check-ignore .venv
```

Expected:

-   `git status` reports a clean working tree after all changes are
    committed.
-   `git ls-files .env` prints nothing.
-   `git check-ignore .env` confirms the local environment file is
    ignored.
-   `git check-ignore .venv` confirms the virtual environment is
    ignored.

Do not commit `.env`, database passwords, API keys, access tokens, or
private certificates.

## 10. What Milestone 1 delivered

-   [x] Monorepo directory structure created.
-   [x] Python virtual environment created.
-   [x] Backend package and dependencies configured.
-   [x] Local environment configuration established.
-   [x] Docker Compose PostgreSQL service running.
-   [x] SQLAlchemy engine and session dependency created.
-   [x] Organization and Project ORM models created.
-   [x] Alembic migration infrastructure configured.
-   [x] Initial database migration applied.
-   [x] FastAPI application created.
-   [x] Root, liveness, and readiness endpoints verified.
-   [x] Organization and project insert/read verified.
-   [x] Initial Git commit created.
-   [x] Main branch pushed to GitHub.

## 11. What is not included yet

The following capabilities are intentionally deferred:

-   Agent registration and discovery.
-   Agent versions and deployment environments.
-   API credential issuance and authentication.
-   Organization membership, users, and RBAC.
-   Agent execution and session tracking.
-   Trace and span persistence.
-   OpenTelemetry Collector and OTLP ingestion.
-   AgentOps telemetry event contracts.
-   Python instrumentation SDK.
-   Tool-call and LLM-call instrumentation.
-   Multi-agent workflow visualization.
-   Token and cost accounting.
-   Evaluation datasets and evaluation runs.
-   Incident detection and alerting.
-   AI-assisted root-cause analysis.
-   Frontend dashboards.
-   Production deployment, autoscaling, and Kubernetes.
-   Production-grade tenant isolation, retention, and audit controls.

The directories for several of these components exist, but the
components themselves have not yet been implemented.

## 12. Engineering concepts learned

  -----------------------------------------------------------------------
  Concept                             Meaning in this project
  ----------------------------------- -----------------------------------
  Monorepo                            Multiple related applications and
                                      packages managed in one repository

  Virtual environment                 Isolated Python dependency
                                      environment

  Editable install                    Install a local package so source
                                      changes are reflected without
                                      reinstalling

  ASGI                                Asynchronous Server Gateway
                                      Interface used by FastAPI/Uvicorn

  ORM                                 Object-relational mapping between
                                      Python classes and database tables

  Engine                              SQLAlchemy's database connectivity
                                      and connection-pool layer

  Session                             Unit of work for database
                                      operations

  Migration                           Version-controlled change to the
                                      database schema

  Foreign key                         Constraint that links a record to
                                      another table

  Unique constraint                   Database rule preventing duplicate
                                      values or combinations

  Health check                        Endpoint used to determine process
                                      liveness or service readiness

  Container                           Isolated runtime environment for a
                                      service

  Named volume                        Persistent Docker-managed storage

  Environment variable                External configuration supplied to
                                      an application

  Tenant                              Customer or organization boundary
                                      in a multi-tenant application
  -----------------------------------------------------------------------

## 13. Milestone 1 completion definition

Milestone 1 is considered complete because the local API starts,
PostgreSQL is healthy, the initial database migration is applied, the
API can verify database connectivity, sample organization/project
records can be persisted and read, and the initial source code is
committed to GitHub.

This milestone establishes the platform foundation only. It does not yet
demonstrate agent observability or monitoring functionality.

**Next milestone:** Milestone 2 --- expand the core data model to
represent environments, agents, agent versions, integrations, sessions,
executions, traces, spans, and telemetry events. Implement each layer
with appropriate tenant ownership, relationships, constraints, and
indexes, then verify it with migrations and API tests.
