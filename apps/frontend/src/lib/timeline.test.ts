import { describe, expect, it } from "vitest";

import { buildTimeline } from "./timeline";
import type { TelemetryEvent } from "./types";

function makeEvent(overrides: Partial<TelemetryEvent>): TelemetryEvent {
  return {
    id: "id-" + Math.random(),
    organization_id: "org-1",
    event_id: "event-" + Math.random(),
    schema_version: "1.0.0",
    event_type: "agent.execution.started",
    occurred_at: "2026-01-01T00:00:00Z",
    received_at: "2026-01-01T00:00:00Z",
    agent_id: "agent-1",
    agent_version_id: null,
    session_id: "session-1",
    execution_id: "execution-1",
    source_platform: "custom-python",
    service_name: "svc",
    environment: "development",
    operation_name: "op",
    operation_kind: "agent",
    operation_status: "started",
    duration_ms: null,
    trace_id: "a".repeat(32),
    span_id: "b".repeat(16),
    parent_span_id: null,
    model_usage: null,
    error: null,
    payload: null,
    attributes: {},
    event_data: {},
    ...overrides,
  };
}

describe("buildTimeline", () => {
  it("sorts events chronologically", () => {
    const events = [
      makeEvent({ id: "later", occurred_at: "2026-01-01T00:00:10Z" }),
      makeEvent({ id: "earlier", occurred_at: "2026-01-01T00:00:00Z" }),
    ];

    const timeline = buildTimeline(events);

    expect(timeline.map((entry) => entry.event.id)).toEqual(["earlier", "later"]);
  });

  it("derives a duration from matching started/completed events sharing a span_id", () => {
    const spanId = "c".repeat(16);
    const events = [
      makeEvent({
        id: "started",
        span_id: spanId,
        operation_status: "started",
        occurred_at: "2026-01-01T00:00:00Z",
        duration_ms: null,
      }),
      makeEvent({
        id: "completed",
        span_id: spanId,
        operation_status: "completed",
        event_type: "agent.execution.completed",
        occurred_at: "2026-01-01T00:00:05Z",
        duration_ms: null,
      }),
    ];

    const timeline = buildTimeline(events);
    const completed = timeline.find((entry) => entry.event.id === "completed")!;

    expect(completed.derivedDurationMs).toBe(5000);
  });

  it("uses the event's own duration_ms when present, without deriving one", () => {
    const events = [makeEvent({ duration_ms: 42 })];
    const timeline = buildTimeline(events);

    expect(timeline[0].derivedDurationMs).toBe(42);
  });

  it("returns null duration when there is no matching counterpart (incomplete trace)", () => {
    const events = [makeEvent({ operation_status: "started", duration_ms: null })];
    const timeline = buildTimeline(events);

    expect(timeline[0].derivedDurationMs).toBeNull();
  });

  it("computes depth from the parent_span_id chain", () => {
    const rootSpan = "root".padEnd(16, "0");
    const childSpan = "child".padEnd(16, "0");
    const grandchildSpan = "gchild".padEnd(16, "0");

    const events = [
      makeEvent({ id: "root", span_id: rootSpan, parent_span_id: null }),
      makeEvent({ id: "child", span_id: childSpan, parent_span_id: rootSpan }),
      makeEvent({ id: "grandchild", span_id: grandchildSpan, parent_span_id: childSpan }),
    ];

    const timeline = buildTimeline(events);
    const byId = Object.fromEntries(timeline.map((entry) => [entry.event.id, entry.depth]));

    expect(byId.root).toBe(0);
    expect(byId.child).toBe(1);
    expect(byId.grandchild).toBe(2);
  });

  it("never invents a relationship when the parent span is missing from this set", () => {
    const events = [
      makeEvent({ id: "orphan", parent_span_id: "nonexistent".padEnd(16, "0") }),
    ];

    const timeline = buildTimeline(events);

    expect(timeline[0].depth).toBe(0);
  });
});
