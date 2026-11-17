
"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Search,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  X,
  RefreshCw,
  LoaderCircle,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import {
  getTelemetryEvents,
  type TelemetryEvent,
} from "@/lib/telemetry";

function formatDate(value: string) {
  return new Date(value).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "medium",
  });
}

function formatDuration(value: number | null) {
  if (value === null) return "—";
  return value < 1000 ? `${value}ms` : `${(value / 1000).toFixed(2)}s`;
}

function getStatusStyle(status: string) {
  switch (status.toLowerCase()) {
    case "completed":
      return "bg-emerald-500/10 text-emerald-400";
    case "failed":
      return "bg-red-500/10 text-red-400";
    case "started":
      return "bg-blue-500/10 text-blue-400";
    default:
      return "bg-slate-500/10 text-slate-400";
  }
}

function MetricCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: number | string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex items-center justify-between text-slate-400">
        <span className="text-sm">{label}</span>
        {icon}
      </div>
      <div className="mt-3 text-3xl font-semibold tabular-nums text-white">
        {value}
      </div>
    </div>
  );
}

function Detail({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-800 pb-3">
      <span className="text-sm text-slate-500">{label}</span>
      <span className={`max-w-[65%] break-all text-right text-sm text-slate-200 ${mono ? "font-mono text-xs" : ""}`}>
        {value}
      </span>
    </div>
  );
}

export default function TelemetryPage() {
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");
  const [selected, setSelected] = useState<TelemetryEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadEvents(nextPage = page) {
    try {
      setLoading(true);
      setError(null);

      const response = await getTelemetryEvents(nextPage, 50);

      setEvents(response.items);
      setTotal(response.total);
      setPage(response.page);
      setTotalPages(response.total_pages);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load telemetry."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadEvents(1);
  }, []);

  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      const query = search.toLowerCase();

      const matchesSearch =
        event.event_id.toLowerCase().includes(query) ||
        event.agent_id.toLowerCase().includes(query) ||
        event.execution_id.toLowerCase().includes(query) ||
        event.operation_name.toLowerCase().includes(query) ||
        event.trace_id.toLowerCase().includes(query);

      const matchesType =
        typeFilter === "All" || event.event_type === typeFilter;

      const matchesStatus =
        statusFilter === "All" ||
        event.operation_status.toLowerCase() === statusFilter;

      return matchesSearch && matchesType && matchesStatus;
    });
  }, [events, search, typeFilter, statusFilter]);

  const successful = events.filter(
    (event) => event.operation_status.toLowerCase() === "completed"
  ).length;

  const failed = events.filter(
    (event) => event.operation_status.toLowerCase() === "failed"
  ).length;

  const tokens = events.reduce(
    (sum, event) => sum + (event.model_usage?.total_tokens ?? 0),
    0
  );

  const eventTypes = [...new Set(events.map((event) => event.event_type))];

  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-white">Telemetry</h1>
            <p className="mt-1 text-sm text-slate-400">
              Inspect agent events, model operations, tool calls and execution signals.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-300">
              Live backend data
            </span>
            <button
              onClick={() => void loadEvents()}
              disabled={loading}
              className="rounded-lg border border-slate-700 p-2 text-slate-400 hover:bg-slate-800"
              title="Refresh telemetry"
            >
              <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Total events" value={total} icon={<Activity size={18} />} />
          <MetricCard label="Successful events" value={successful} icon={<CheckCircle2 size={18} />} />
          <MetricCard label="Failed events" value={failed} icon={<AlertTriangle size={18} />} />
          <MetricCard label="LLM tokens" value={tokens.toLocaleString()} icon={<Cpu size={18} />} />
        </div>

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4">
            <p className="text-sm font-medium text-red-400">Telemetry API error</p>
            <p className="mt-1 break-words text-sm text-red-300">{error}</p>
            <button
              onClick={() => void loadEvents()}
              className="mt-3 text-sm text-red-300 underline"
            >
              Retry
            </button>
          </div>
        )}

        <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">
          <div className="flex flex-col gap-3 border-b border-slate-800 p-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <h2 className="font-semibold text-white">Event stream</h2>
              <p className="mt-1 text-xs text-slate-400">
                {filteredEvents.length} events displayed · {total} total
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <div className="relative min-w-52 flex-1">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search event, agent, execution..."
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 py-2 pl-9 pr-3 text-sm text-white outline-none focus:border-blue-500"
                />
              </div>

              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="max-w-64 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-300 outline-none"
              >
                <option value="All">All event types</option>
                {eventTypes.map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-300 outline-none"
              >
                <option value="All">All statuses</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
                <option value="started">Started</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[1050px] text-left text-sm">
              <thead className="bg-slate-950/70 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Event ID</th>
                  <th className="px-5 py-3 font-medium">Event type</th>
                  <th className="px-5 py-3 font-medium">Agent ID</th>
                  <th className="px-5 py-3 font-medium">Operation</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Duration</th>
                  <th className="px-5 py-3 font-medium">Tokens</th>
                  <th className="px-5 py-3 font-medium">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {loading ? (
                  <tr>
                    <td colSpan={8} className="px-5 py-12 text-center text-slate-400">
                      <LoaderCircle size={20} className="mx-auto mb-2 animate-spin" />
                      Loading telemetry...
                    </td>
                  </tr>
                ) : filteredEvents.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-5 py-14 text-center">
                      <Activity size={26} className="mx-auto mb-3 text-slate-600" />
                      <p className="font-medium text-slate-300">
                        {error ? "Telemetry could not be loaded." : "No telemetry events found"}
                      </p>
                      <p className="mt-2 text-sm text-slate-500">
                        {error
                          ? "Check the API connection and retry."
                          : "Your database currently has no telemetry events. Instrument an agent to start collecting events."}
                      </p>
                    </td>
                  </tr>
                ) : (
                  filteredEvents.map((event) => (
                    <tr
                      key={event.event_id}
                      onClick={() => setSelected(event)}
                      className="cursor-pointer transition hover:bg-slate-800/50"
                    >
                      <td className="px-5 py-4 font-mono text-xs text-blue-400">
                        {event.event_id.slice(0, 13)}...
                      </td>
                      <td className="px-5 py-4 text-xs text-violet-300">
                        {event.event_type}
                      </td>
                      <td className="px-5 py-4 font-mono text-xs text-slate-400">
                        {event.agent_id.slice(0, 13)}...
                      </td>
                      <td className="px-5 py-4 text-slate-300">
                        {event.operation_name}
                      </td>
                      <td className="px-5 py-4">
                        <span className={`rounded-full px-2.5 py-1 text-xs ${getStatusStyle(event.operation_status)}`}>
                          {event.operation_status}
                        </span>
                      </td>
                      <td className="px-5 py-4 tabular-nums text-slate-300">
                        {formatDuration(event.duration_ms)}
                      </td>
                      <td className="px-5 py-4 tabular-nums text-slate-300">
                        {event.model_usage?.total_tokens ?? "—"}
                      </td>
                      <td className="px-5 py-4 text-xs text-slate-400">
                        {formatDate(event.occurred_at)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-800 p-4">
              <span className="text-xs text-slate-500">
                Page {page} of {totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1 || loading}
                  onClick={() => void loadEvents(page - 1)}
                  className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  disabled={page >= totalPages || loading}
                  onClick={() => void loadEvents(page + 1)}
                  className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </section>

        {selected && (
          <div
            className="fixed inset-0 z-50 flex justify-end bg-black/60"
            onClick={() => setSelected(null)}
          >
            <aside
              onClick={(e) => e.stopPropagation()}
              className="h-full w-full max-w-xl overflow-y-auto border-l border-slate-800 bg-slate-950 p-6 shadow-2xl"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Telemetry event</p>
                  <h2 className="mt-1 break-all font-mono text-lg text-white">
                    {selected.event_id}
                  </h2>
                </div>
                <button
                  onClick={() => setSelected(null)}
                  className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="mt-7 space-y-4">
                <Detail label="Event type" value={selected.event_type} />
                <Detail label="Agent ID" value={selected.agent_id} mono />
                <Detail label="Execution ID" value={selected.execution_id} mono />
                <Detail label="Trace ID" value={selected.trace_id} mono />
                <Detail label="Span ID" value={selected.span_id} mono />
                <Detail label="Parent span ID" value={selected.parent_span_id || "None"} mono />
                <Detail label="Operation" value={selected.operation_name} />
                <Detail label="Operation kind" value={selected.operation_kind} />
                <Detail label="Status" value={selected.operation_status} />
                <Detail label="Environment" value={selected.environment} />
                <Detail label="Source platform" value={selected.source_platform} />
                <Detail label="Service" value={selected.service_name} />
                <Detail label="Occurred at" value={formatDate(selected.occurred_at)} />
                <Detail label="Received at" value={formatDate(selected.received_at)} />
                <Detail label="Duration" value={formatDuration(selected.duration_ms)} />

                {selected.model_usage && (
                  <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                    <h3 className="mb-3 text-sm font-medium text-slate-200">Model usage</h3>
                    <Detail label="Provider" value={selected.model_usage.provider || "—"} />
                    <Detail label="Model" value={selected.model_usage.model || "—"} />
                    <Detail label="Input tokens" value={String(selected.model_usage.input_tokens ?? "—")} />
                    <Detail label="Output tokens" value={String(selected.model_usage.output_tokens ?? "—")} />
                    <Detail label="Total tokens" value={String(selected.model_usage.total_tokens ?? "—")} />
                    <Detail label="Cost (USD)" value={String(selected.model_usage.cost_usd ?? "—")} />
                  </div>
                )}

                {selected.error && (
                  <div>
                    <h3 className="mb-2 text-sm font-medium text-red-400">Error information</h3>
                    <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-xs leading-6 text-red-300">
                      {JSON.stringify(selected.error, null, 2)}
                    </pre>
                  </div>
                )}

                <div>
                  <h3 className="mb-2 text-sm font-medium text-slate-300">Attributes</h3>
                  <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border border-slate-800 bg-slate-900 p-3 text-xs leading-6 text-slate-400">
                    {JSON.stringify(selected.attributes, null, 2)}
                  </pre>
                </div>
              </div>
            </aside>
          </div>
        )}
      </div>
    </AppShell>
  );
}
