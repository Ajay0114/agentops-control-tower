import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";

import { renderAsync } from "@/test/render-async";
import ExecutionDetailPage from "./page";
import { ApiClientError } from "@/lib/api/client";
import type { ExecutionResponse, TelemetryEvent, TelemetryEventListResponse } from "@/lib/types";

const fetchExecutionMock = vi.fn();
const fetchExecutionEventsMock = vi.fn();

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return {
    ...actual,
    fetchExecution: (...args: unknown[]) => fetchExecutionMock(...args),
    fetchExecutionEvents: (...args: unknown[]) => fetchExecutionEventsMock(...args),
  };
});

function makeExecution(overrides: Partial<ExecutionResponse> = {}): ExecutionResponse {
  return {
    id: "exec-1",
    session_id: "session-1",
    agent_id: "agent-1",
    agent_version_id: null,
    external_execution_id: "ext-1",
    status: "completed",
    started_at: "2026-01-01T00:00:00Z",
    ended_at: "2026-01-01T00:00:05Z",
    duration_ms: 5000,
    error_type: null,
    error_message: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:05Z",
    ...overrides,
  };
}

function makeEvent(overrides: Partial<TelemetryEvent> = {}): TelemetryEvent {
  return {
    id: "event-1",
    organization_id: "org-1",
    event_id: "evt-1",
    schema_version: "1.0.0",
    event_type: "llm.request.completed",
    occurred_at: "2026-01-01T00:00:01Z",
    received_at: "2026-01-01T00:00:01Z",
    agent_id: "agent-1",
    agent_version_id: null,
    session_id: "session-1",
    execution_id: "exec-1",
    source_platform: "custom-python",
    service_name: "svc",
    environment: "development",
    operation_name: "gpt-4",
    operation_kind: "llm",
    operation_status: "completed",
    duration_ms: 200,
    trace_id: "a".repeat(32),
    span_id: "b".repeat(16),
    parent_span_id: null,
    model_usage: { provider: "openai", model: "gpt-4", total_tokens: 42 },
    error: null,
    payload: null,
    attributes: {},
    event_data: {},
    ...overrides,
  };
}

beforeEach(() => {
  fetchExecutionMock.mockReset();
  fetchExecutionEventsMock.mockReset();
});

describe("ExecutionDetailPage", () => {
  it("renders execution metadata and the event timeline", async () => {
    fetchExecutionMock.mockResolvedValue(makeExecution());
    const eventResponse: TelemetryEventListResponse = {
      items: [makeEvent()],
      total: 1,
      page: 1,
      page_size: 200,
      total_pages: 1,
    };
    fetchExecutionEventsMock.mockResolvedValue(eventResponse);

    await renderAsync(<ExecutionDetailPage params={Promise.resolve({ id: "exec-1" })} />);

    await waitFor(() => expect(screen.getByText("gpt-4")).toBeInTheDocument());
    expect(screen.getByText(/Total tokens: 42/)).toBeInTheDocument();
  });

  it("shows an empty state when there are no telemetry events yet", async () => {
    fetchExecutionMock.mockResolvedValue(makeExecution());
    fetchExecutionEventsMock.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200, total_pages: 0 });

    await renderAsync(<ExecutionDetailPage params={Promise.resolve({ id: "exec-1" })} />);

    await waitFor(() => expect(screen.getByText("No telemetry events yet")).toBeInTheDocument());
  });

  it("shows a not-found message for a 404", async () => {
    fetchExecutionMock.mockRejectedValue(new ApiClientError(404, "Execution not found"));
    fetchExecutionEventsMock.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200, total_pages: 0 });

    await renderAsync(<ExecutionDetailPage params={Promise.resolve({ id: "missing" })} />);

    await waitFor(() => expect(screen.getByText("Execution not found")).toBeInTheDocument());
  });

  it("surfaces the execution's own error metadata when it failed", async () => {
    fetchExecutionMock.mockResolvedValue(
      makeExecution({ status: "failed", error_type: "ValueError", error_message: "bad input" })
    );
    fetchExecutionEventsMock.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200, total_pages: 0 });

    await renderAsync(<ExecutionDetailPage params={Promise.resolve({ id: "exec-1" })} />);

    await waitFor(() => expect(screen.getByText(/bad input/)).toBeInTheDocument());
  });
});
