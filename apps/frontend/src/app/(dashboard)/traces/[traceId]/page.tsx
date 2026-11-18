
"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { fetchTraceEvents, ApiClientError } from "@/lib/api/client";
import { buildTimeline } from "@/lib/timeline";
import EventRow from "@/components/telemetry/event-row";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/ui/states";
import type { TelemetryEvent } from "@/lib/types";

export default function TraceDetailPage({ params }: { params: Promise<{ traceId: string }> }) {
  const { traceId } = use(params);

  const [events, setEvents] = useState<TelemetryEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTraceEvents(traceId, { page_size: 200 })
      .then((data) => setEvents(data.items))
      .catch((err) => setError(err instanceof ApiClientError ? err.detail : "Failed to load trace"));
  }, [traceId]);

  if (error) return <div className="p-6"><ErrorState message={error} /></div>;
  if (events === null) return <div className="p-6"><LoadingSkeleton rows={5} /></div>;

  const timeline = buildTimeline(events);
  const executionId = events[0]?.execution_id ?? null;

  return (
    <div className="space-y-6 p-6">
      <Link href="/traces" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={14} /> Back to traces
      </Link>

      <div>
        <h1 className="font-mono text-lg font-semibold text-slate-100">{traceId}</h1>
        {executionId && (
          <p className="text-sm text-slate-400">
            Execution{" "}
            <Link href={`/executions/${executionId}`} className="text-blue-400 hover:underline">
              {executionId.slice(0, 8)}
            </Link>
          </p>
        )}
      </div>

      {timeline.length === 0 ? (
        <EmptyState
          title="No events found for this trace"
          description="The trace ID may be invalid, or outside your authorized scope."
        />
      ) : (
        <div className="space-y-2">
          {timeline.map((entry) => (
            <EventRow key={entry.event.id} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}
