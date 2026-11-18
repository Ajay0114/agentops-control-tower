
"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { fetchExecution, fetchExecutionEvents, ApiClientError } from "@/lib/api/client";
import { formatDateTime, formatDuration } from "@/lib/format";
import { buildTimeline } from "@/lib/timeline";
import StatusBadge from "@/components/ui/status-badge";
import EventRow from "@/components/telemetry/event-row";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/ui/states";
import type { ExecutionResponse, TelemetryEvent } from "@/lib/types";

export default function ExecutionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const [execution, setExecution] = useState<ExecutionResponse | null>(null);
  const [events, setEvents] = useState<TelemetryEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchExecution(id), fetchExecutionEvents(id, { page_size: 200 })])
      .then(([executionData, eventData]) => {
        setExecution(executionData);
        setEvents(eventData.items);
      })
      .catch((err) =>
        setError(
          err instanceof ApiClientError
            ? err.status === 404
              ? "Execution not found"
              : err.detail
            : "Failed to load execution"
        )
      );
  }, [id]);

  if (error) return <div className="p-6"><ErrorState message={error} /></div>;
  if (!execution) return <div className="p-6"><LoadingSkeleton rows={6} /></div>;

  const timeline = events ? buildTimeline(events) : [];
  const traceId = events?.[0]?.trace_id ?? null;

  return (
    <div className="space-y-6 p-6">
      <Link href="/executions" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={14} /> Back to executions
      </Link>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-mono text-lg font-semibold text-slate-100">{execution.id}</h1>
          <p className="text-sm text-slate-400">
            Agent{" "}
            <Link href={`/agents/${execution.agent_id}`} className="text-blue-400 hover:underline">
              {execution.agent_id.slice(0, 8)}
            </Link>{" "}
            · Session{" "}
            <Link href={`/sessions/${execution.session_id}`} className="text-blue-400 hover:underline">
              {execution.session_id.slice(0, 8)}
            </Link>
          </p>
        </div>
        <StatusBadge status={execution.status} />
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-lg border border-slate-800 bg-slate-900/60 p-4 md:grid-cols-4">
        <div>
          <div className="text-xs uppercase text-slate-500">Started</div>
          <div className="mt-1 text-slate-200">{formatDateTime(execution.started_at)}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Ended</div>
          <div className="mt-1 text-slate-200">{formatDateTime(execution.ended_at)}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Duration</div>
          <div className="mt-1 text-slate-200">{formatDuration(execution.duration_ms)}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Trace</div>
          {traceId ? (
            <Link href={`/traces/${traceId}`} className="mt-1 block font-mono text-xs text-blue-400 hover:underline">
              {traceId.slice(0, 12)}…
            </Link>
          ) : (
            <div className="mt-1 text-slate-500">No telemetry yet</div>
          )}
        </div>
      </div>

      {execution.status === "failed" && execution.error_message && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-300">
          <span className="font-medium">{execution.error_type}:</span> {execution.error_message}
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium text-slate-300">Event timeline</h2>
          {traceId && (
            <Link href={`/traces/${traceId}`} className="text-xs text-blue-400 hover:underline">
              View as trace tree
            </Link>
          )}
        </div>

        {events === null ? (
          <LoadingSkeleton rows={4} />
        ) : timeline.length === 0 ? (
          <EmptyState
            title="No telemetry events yet"
            description="Events appear here as the SDK reports traces, LLM calls, and tool calls for this execution."
          />
        ) : (
          <div className="space-y-2">
            {timeline.map((entry) => (
              <EventRow key={entry.event.id} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
