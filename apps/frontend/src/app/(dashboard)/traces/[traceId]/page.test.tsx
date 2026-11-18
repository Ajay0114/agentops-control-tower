import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";

import { renderAsync } from "@/test/render-async";
import TraceDetailPage from "./page";
import type { TelemetryEvent } from "@/lib/types";

const fetchTraceEventsMock = vi.fn();

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return { ...actual, fetchTraceEvents: (...args: unknown[]) => fetchTraceEventsMock(...args) };
});

function makeEvent(overrides: Partial<TelemetryEvent> = {}): TelemetryEvent {
  return {
    id: "event-1",
    organization_id: "org-1",
    event_id: "evt-1",
    schema_version: "1.0.0",
    event_type: "agent.execution.started",
    occurred_at: "2026-01-01T00:00:00Z",
    received_at: "2026-01-01T00:00:00Z",
    agent_id: "agent-1",
    agent_version_id: null,
    session_id: "session-1",
    execution_id: "exec-1",
    source_platform: "custom-python",
    service_name: "svc",
    environment: "development",
    operation_name: "agent_execution",
    operation_kind: "agent",
    operation_status: "started",
    duration_ms: null,
    trace_id: "a".repeat(32),
    span_id: "root".padEnd(16, "0"),
    parent_span_id: null,
    model_usage: null,
    error: null,
    payload: null,
    attributes: {},
    event_data: {},
    ...overrides,
  };
}

beforeEach(() => {
  fetchTraceEventsMock.mockReset();
});

describe("TraceDetailPage", () => {
  it("renders the span hierarchy with indentation reflecting parent/child depth", async () => {
    const rootSpan = "root".padEnd(16, "0");
    const childSpan = "child".padEnd(16, "0");

    fetchTraceEventsMock.mockResolvedValue({
      items: [
        makeEvent({ id: "root-event", span_id: rootSpan, operation_name: "agent_execution" }),
        makeEvent({
          id: "child-event",
          span_id: childSpan,
          parent_span_id: rootSpan,
          operation_name: "lookup_order",
          operation_kind: "tool",
        }),
      ],
      total: 2,
      page: 1,
      page_size: 200,
      total_pages: 1,
    });

    await renderAsync(<TraceDetailPage params={Promise.resolve({ traceId: "a".repeat(32) })} />);

    await waitFor(() => expect(screen.getByText("lookup_order")).toBeInTheDocument());
    expect(screen.getByText("agent_execution")).toBeInTheDocument();

    // Linked back to the shared execution_id.
    expect(screen.getByRole("link", { name: /exec-1/ })).toHaveAttribute(
      "href",
      "/executions/exec-1"
    );
  });

  it("shows an empty state for a trace with no events", async () => {
    fetchTraceEventsMock.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 200,
      total_pages: 0,
    });

    await renderAsync(<TraceDetailPage params={Promise.resolve({ traceId: "a".repeat(32) })} />);

    await waitFor(() =>
      expect(screen.getByText("No events found for this trace")).toBeInTheDocument()
    );
  });
});
