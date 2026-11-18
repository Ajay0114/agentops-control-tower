import StatusBadge from "@/components/ui/status-badge";
import { formatDateTime, formatDuration, formatTokenCount } from "@/lib/format";
import type { TimelineEntry } from "@/lib/timeline";

const KIND_LABELS: Record<string, string> = {
  agent: "Agent",
  llm: "LLM call",
  tool: "Tool call",
  workflow: "Workflow",
  state: "State",
};

export default function EventRow({ entry }: { entry: TimelineEntry }) {
  const { event, depth, derivedDurationMs } = entry;

  return (
    <div
      className="rounded-md border border-slate-800 bg-slate-900/40 p-3"
      style={{ marginLeft: depth * 20 }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
          {KIND_LABELS[event.operation_kind] ?? event.operation_kind}
        </span>
        <span className="font-medium text-slate-200">{event.operation_name}</span>
        <StatusBadge status={event.operation_status} />
        <span className="ml-auto text-xs text-slate-500">{formatDateTime(event.occurred_at)}</span>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        <span>Duration: {formatDuration(derivedDurationMs)}</span>
        <span className="font-mono">span: {event.span_id.slice(0, 10)}</span>
        {event.parent_span_id && (
          <span className="font-mono">parent: {event.parent_span_id.slice(0, 10)}</span>
        )}
      </div>

      {event.model_usage && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 rounded bg-slate-950/60 p-2 text-xs text-slate-400">
          {event.model_usage.provider && <span>Provider: {event.model_usage.provider}</span>}
          {event.model_usage.model && <span>Model: {event.model_usage.model}</span>}
          {event.model_usage.input_tokens != null && (
            <span>Input tokens: {formatTokenCount(event.model_usage.input_tokens)}</span>
          )}
          {event.model_usage.output_tokens != null && (
            <span>Output tokens: {formatTokenCount(event.model_usage.output_tokens)}</span>
          )}
          {event.model_usage.total_tokens != null && (
            <span>Total tokens: {formatTokenCount(event.model_usage.total_tokens)}</span>
          )}
          {event.model_usage.cost_usd != null && <span>Cost: ${event.model_usage.cost_usd}</span>}
        </div>
      )}

      {event.error && (
        <div className="mt-2 rounded bg-red-500/5 p-2 text-xs text-red-300">
          <span className="font-medium">{event.error.type}:</span> {event.error.message}
        </div>
      )}

      {event.attributes && Object.keys(event.attributes).length > 0 && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
          {/* Always safe metadata by construction - the telemetry contract
              never carries raw prompts/completions/tool payloads (see
              docs/architecture/telemetry-event-contract.md); e.g. a tool
              call's "input"/"output" attribute is only {type, size}. */}
          {Object.entries(event.attributes).map(([key, value]) => (
            <span key={key}>
              {key}: {typeof value === "object" ? JSON.stringify(value) : String(value)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
