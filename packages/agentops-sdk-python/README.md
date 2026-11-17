# agentops-sdk

Python SDK for [AgentOps Control Tower](../../Readme.md): framework-independent
observability and governance for AI agents. Works with any agent code - no
coupling to a specific LLM provider, orchestration framework, or runtime.

- **Sync and async**: `AgentOps` and `AsyncAgentOps` offer the same API shape.
- **Execution, trace and span tracking**: nested spans use `contextvars`, so
  context propagates correctly across concurrent `asyncio` tasks and threads.
- **LLM and tool instrumentation**: structured usage/metadata only.
- **Privacy by default**: the SDK never transmits raw prompts, completions,
  chain-of-thought, or raw tool payloads - only metadata (type/size/tokens).

## Installation

From the monorepo root, in a virtual environment:

```bash
pip install -e packages/agentops-sdk-python
```

For running the SDK's own test suite:

```bash
pip install -e "packages/agentops-sdk-python[dev]"
```

## Prerequisite: register your agent

The SDK identifies an **existing** agent - it never creates or provisions one.
Register your agent and get an API key through the existing admin tooling
(Agent Registry API / admin CLI) before using the SDK:

1. Create an `Environment` and `Agent` (and optionally an `AgentVersion`)
   through the Agent Registry API.
2. Provision an API key with `apps/api/src/agentops_api/scripts/provision_api_key.py`
   (or the equivalent registry endpoint).

You'll need the agent's `agent_id` (UUID) and the API key at runtime.

## Configuration

```python
from agentops_sdk import AgentOps

agentops = AgentOps(
    endpoint="https://api.agentops.example.com",  # your AgentOps API base URL
    api_key="aops_...",                            # never logged by the SDK
    agent_id="3fbe2b8e-...",                       # optional default agent
    environment="production",                     # free-text label (telemetry only)
    service_name="checkout-agent",                 # identifies this process
    capture_mode="metadata_only",                  # or "redacted" (see Privacy)
    timeout=5.0,
    max_retries=3,
    batch_size=50,
    flush_interval=5.0,
)
```

| Parameter        | Default              | Meaning                                                              |
|------------------|----------------------|------------------------------------------------------------------------|
| `endpoint`       | *required*            | AgentOps API base URL (`http://` or `https://`).                      |
| `api_key`        | *required*            | Bearer API key. Never logged.                                         |
| `agent_id`       | `None`                | Default agent id, used when `agent()` is called with no id.           |
| `environment`    | `"development"`       | Free-text label stored as telemetry's `source.environment`.           |
| `service_name`   | `"agentops-sdk-python"` | Identifies the calling process/service in telemetry.                |
| `capture_mode`   | `"metadata_only"`      | `"metadata_only"` or `"redacted"`. `"restricted"` is not available yet. |
| `timeout`        | `5.0`                  | Per-request HTTP timeout (seconds).                                   |
| `max_retries`    | `3`                    | Retries for transient failures (connection errors, 429, 5xx).         |
| `batch_size`     | `50`                   | Telemetry events per delivery batch.                                  |
| `flush_interval` | `5.0`                  | Max seconds telemetry waits in the queue before a batch is sent.      |
| `http_client`    | `None`                 | Your own `httpx.Client` (or `httpx.AsyncClient` for `AsyncAgentOps`) - see below. |

Every parameter can also be read from your own environment/config loader; the
SDK does not read environment variables itself, so there's one obvious place
(your own startup code) that owns configuration.

### Custom HTTP client

Pass your own pre-configured `httpx.Client` (or `httpx.AsyncClient`) when you
need custom proxies, TLS/CA settings, connection limits, or transport mounts.
The SDK applies its own base URL and `Authorization` header per-request -
it never overwrites the client's own default headers or `base_url` - so it's
safe to pass a client you also use for other, unrelated HTTP calls. A client
you supply is never closed by `shutdown()` - you own its lifecycle:

```python
import httpx
from agentops_sdk import AgentOps

my_client = httpx.Client(proxy="http://localhost:3128", limits=httpx.Limits(max_connections=20))
agentops = AgentOps(endpoint="...", api_key="...", http_client=my_client)
...
agentops.shutdown()  # does not close my_client
my_client.close()    # your responsibility
```

## Quick start

```python
from agentops_sdk import AgentOps

agentops = AgentOps(endpoint="https://api.agentops.example.com", api_key="aops_...")

agent = agentops.agent("3fbe2b8e-your-agent-id", version="1.4.0")

with agentops.start_execution(agent=agent, session_id="conversation-123") as execution:
    execution.set_output("Order #4821 confirmed.")  # local only, never transmitted

agentops.shutdown()
```

Entering `start_execution(...)`'s `with` block transitions the execution to
`running` and emits `agent.execution.started`; exiting emits
`agent.execution.completed` (or `agent.execution.failed`, if the block raised -
the exception is always re-raised, never swallowed).

## Complete agent example

```python
from agentops_sdk import AgentOps

agentops = AgentOps(
    endpoint="https://api.agentops.example.com",
    api_key="aops_...",
    environment="production",
    service_name="support-agent",
)

agent = agentops.agent("3fbe2b8e-your-agent-id", version="1.4.0")

def handle_message(session_id: str, user_message: str) -> str:
    with agentops.start_execution(agent=agent, session_id=session_id) as execution:
        with execution.trace("classify_intent"):
            intent = classify(user_message)

        with execution.llm_call(model="gpt-4.1", provider="openai") as call:
            reply = call_llm(user_message, intent)
            call.set_usage(input_tokens=reply.usage.prompt, output_tokens=reply.usage.completion)

        with execution.tool_call("lookup_order") as tool:
            tool.set_input({"order_id": intent.order_id})
            result = lookup_order(intent.order_id)
            tool.set_output(result)

        execution.state_changed("order_status", status=result["status"])
        execution.set_output(reply.text)
        return reply.text

try:
    handle_message("conversation-123", "Where is my order?")
finally:
    agentops.shutdown()
```

`with agentops:` / `AgentOps(...) as agentops:` is also supported and calls
`shutdown()` on exit.

## LLM instrumentation

`execution.llm_call(model=, provider=)` never captures prompts or completions -
only structured usage you explicitly report via `set_usage`:

```python
with execution.llm_call(model="claude-sonnet-5", provider="anthropic") as call:
    response = client.messages.create(...)
    call.set_usage(
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cost_usd=0.0021,  # optional; the SDK never estimates cost on its own
    )
# total_tokens is computed automatically from input + output when you don't pass it.
```

An exception raised inside the block is captured as a failed `llm.request.failed`
event (type + message only) and re-raised; call `call.fail(error)` instead if
your LLM client reports failure through a return value rather than raising.

## Tool instrumentation

`execution.tool_call(name)` records only safe metadata about inputs/outputs -
their type and size - never their contents:

```python
with execution.tool_call("search_catalog") as tool:
    tool.set_input(query)          # recorded as {"type": "str", "size": 12}
    results = search_catalog(query)
    tool.set_output(results)       # recorded as {"type": "list", "size": 5}
```

## Async usage

`AsyncAgentOps` mirrors `AgentOps`. `track()` never blocks (safe to call
without `await`); `agent()` and `start_execution()` are coroutines you must
await, and the `Execution`/`Span`/`LLMCall`/`ToolCall` objects they produce
support `async with` directly:

```python
import asyncio
from agentops_sdk import AsyncAgentOps

async def main():
    agentops = AsyncAgentOps(endpoint="https://api.agentops.example.com", api_key="aops_...")
    agent = await agentops.agent("3fbe2b8e-your-agent-id")

    execution = await agentops.start_execution(agent=agent, session_id="conversation-123")
    async with execution:
        async with execution.llm_call(model="gpt-4.1", provider="openai") as call:
            response = await call_llm_async(...)
            call.set_usage(input_tokens=response.usage.prompt, output_tokens=response.usage.completion)

    await agentops.shutdown()

asyncio.run(main())
```

Concurrent executions on the same `AsyncAgentOps` instance (e.g. via
`asyncio.gather`) are fully isolated: each task's spans use their own
`contextvars` context, so nested traces never leak between concurrent
executions, even though telemetry delivery itself is shared.

## Error handling

All SDK exceptions derive from `AgentOpsError`:

```python
from agentops_sdk import (
    AgentOps,
    AgentOpsAuthenticationError,
    AgentOpsConflictError,
    AgentOpsNotFoundError,
    AgentOpsTransportError,
    AgentOpsValidationError,
)

agentops = AgentOps(endpoint="...", api_key="...")

try:
    agent = agentops.agent("not-a-real-agent-id")
except AgentOpsNotFoundError:
    # The agent doesn't exist, or isn't visible to this API key's tenant scope.
    ...
except AgentOpsAuthenticationError:
    # The API key is missing, invalid, or revoked.
    ...
except AgentOpsTransportError as exc:
    # Any other request failure. exc.retryable tells you whether the SDK
    # already exhausted its own retries (max_retries) for a transient error.
    ...
```

| Exception                     | Cause                                                         | Retried by the SDK? |
|--------------------------------|----------------------------------------------------------------|----------------------|
| `AgentOpsConfigurationError`    | Invalid constructor arguments.                                 | n/a                  |
| `AgentOpsAuthenticationError`   | HTTP 401/403.                                                   | No                   |
| `AgentOpsNotFoundError`         | HTTP 404 (not found, or outside your tenant scope).            | No                   |
| `AgentOpsConflictError`         | HTTP 409 (idempotency/uniqueness conflict).                    | No                   |
| `AgentOpsValidationError`       | HTTP 422 (request rejected as invalid).                        | No                   |
| `AgentOpsTransportError`        | Connection errors, HTTP 429, HTTP 5xx, or other request failures. | Yes, up to `max_retries`, with exponential backoff and jitter |
| `AgentOpsShutdownError`         | The client was used after `shutdown()`.                        | n/a                  |

`agent()` and `start_execution()`'s control-plane calls (resolving an agent,
creating a session/execution, transitioning status) raise these exceptions
directly. Telemetry delivery (`track`/the spans' own events) never raises into
your code - it logs and drops the event instead, so instrumentation can never
crash your agent.

### Idempotency

- `start_execution(..., external_execution_id="my-stable-id")`: pass your own
  stable id so retried calls (yours, not the SDK's) that are logically the
  same execution are recognized as one by the backend's idempotency check.
- Without an explicit id, the SDK generates one per `start_execution()` call.
  Retries *within* that one call (e.g. the control-plane request retrying on a
  5xx) always reuse the same id, so they never create a duplicate execution.

## Privacy and security

- **The API key is never logged.** It's only ever sent as the `Authorization`
  header.
- **No raw content is ever transmitted**, in any capture mode: no prompts, no
  completions, no chain-of-thought, no raw tool inputs/outputs. `ToolCall`
  records only `{"type": ..., "size": ...}` for whatever you pass to
  `set_input`/`set_output`. `LLMCall` has no input/output capture methods at
  all - only `set_usage()`.
- **`capture_mode`** (`metadata_only`, the default, or `redacted`) is recorded
  on every telemetry event's `payload.capture_mode` field for audit purposes;
  it does not change *what* the SDK captures (always metadata-only) - it
  documents the capture policy in effect for downstream consumers of the
  telemetry. `"restricted"` is reserved for a future authorization mechanism
  and is rejected at configuration time.
- **`Execution.set_output(...)`** is local-only bookkeeping (e.g. for your own
  logs) - it is never transmitted to AgentOps.
- The SDK does not create agents, environments, or API keys. Provisioning
  stays with your existing admin tooling, keeping credential issuance in one
  place.

## Backend compatibility

The SDK speaks the existing Agent Registry, Session, Execution and Telemetry
APIs exactly as committed - no new backend endpoints were introduced or
required. It is verified against a live instance of the backend (not just
mocks) in `tests/test_sdk_integration.py` at the repository root.

## Known limitations

- `capture_mode="restricted"` is not available yet (raises
  `AgentOpsConfigurationError` at construction time).
- There is no `agent.execution.cancelled` telemetry event in the current
  Telemetry Event Contract (v1.0.0); `Execution.cancel()` /
  `AsyncExecution.cancel()` update the registry's execution status only.
- Framework-specific adapters (OpenAI, LangGraph, Microsoft Agent Framework,
  Azure AI Foundry, Kore.ai, etc.) are out of scope for this package - the
  core SDK has no dependency on any of them, by design.
