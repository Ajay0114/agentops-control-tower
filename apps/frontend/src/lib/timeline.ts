import type { TelemetryEvent } from "./types";

export interface TimelineEntry {
  event: TelemetryEvent;
  depth: number;
  derivedDurationMs: number | null;
}

/**
 * Builds a chronological timeline from a flat list of telemetry events,
 * deriving a duration for events that don't carry duration_ms themselves
 * (the execution-level started/completed pair has none - see
 * execution.py's _terminal_event) by matching them to a same-span_id
 * counterpart, and a display depth from each event's parent_span_id chain.
 * Never invents a parent/child relationship where the identifiers
 * themselves don't establish one - an event whose parent_span_id isn't
 * among the fetched events is simply shown at depth 0 (see M7's "do not
 * invent relationships where parent/span identifiers are missing").
 */
export function buildTimeline(events: TelemetryEvent[]): TimelineEntry[] {
  const bySpanId = new Map<string, TelemetryEvent[]>();

  for (const event of events) {
    const group = bySpanId.get(event.span_id) ?? [];
    group.push(event);
    bySpanId.set(event.span_id, group);
  }

  const knownSpanIds = new Set(events.map((event) => event.span_id));

  function depthOf(event: TelemetryEvent, seen = new Set<string>()): number {
    if (!event.parent_span_id || seen.has(event.span_id)) return 0;
    if (!knownSpanIds.has(event.parent_span_id)) return 0;

    const parentEvent = events.find((candidate) => candidate.span_id === event.parent_span_id);
    if (!parentEvent) return 0;

    seen.add(event.span_id);
    return 1 + depthOf(parentEvent, seen);
  }

  function derivedDuration(event: TelemetryEvent): number | null {
    if (event.duration_ms !== null) return event.duration_ms;

    const siblings = bySpanId.get(event.span_id) ?? [];
    const started = siblings.find((candidate) => candidate.operation_status === "started");
    const terminal = siblings.find(
      (candidate) => candidate.operation_status === "completed" || candidate.operation_status === "failed"
    );

    if (!started || !terminal) return null;

    return Math.max(
      0,
      new Date(terminal.occurred_at).getTime() - new Date(started.occurred_at).getTime()
    );
  }

  return [...events]
    .sort((a, b) => new Date(a.occurred_at).getTime() - new Date(b.occurred_at).getTime())
    .map((event) => ({
      event,
      depth: depthOf(event),
      derivedDurationMs: derivedDuration(event),
    }));
}
