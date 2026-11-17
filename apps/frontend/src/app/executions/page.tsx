
"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Search,
  Activity,
  CheckCircle2,
  XCircle,
  LoaderCircle,
  Clock3,
  X,
  ArrowUpRight,
  RefreshCw,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import {
  getExecutions,
  getExecution,
  type ExecutionResponse,
  type ExecutionStatus,
} from "@/lib/executions";

function formatDate(value: string | null): string {
  if (!value) return "Not started";

  return new Date(value).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "medium",
  });
}

function formatDuration(value: number | null): string {
  if (value === null) return "—";
  if (value < 1000) return `${value}ms`;
  return `${(value / 1000).toFixed(2)}s`;
}

function displayStatus(status: ExecutionStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

const statusStyles: Record<ExecutionStatus, string> = {
  completed: "bg-emerald-500/10 text-emerald-400",
  failed: "bg-red-500/10 text-red-400",
  running: "bg-blue-500/10 text-blue-400",
  queued: "bg-amber-500/10 text-amber-400",
  cancelled: "bg-slate-500/10 text-slate-400",
};

function StatusBadge({ status }: { status: ExecutionStatus }) {
  const icons = {
    completed: <CheckCircle2 size={13} />,
    failed: <XCircle size={13} />,
    running: <LoaderCircle size={13} className="animate-spin" />,
    queued: <Clock3 size={13} />,
    cancelled: <XCircle size={13} />,
  };

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${statusStyles[status]}`}>
      {icons[status]}
      {displayStatus(status)}
    </span>
  );
}

export default function ExecutionsPage() {
  const [executions, setExecutions] = useState<ExecutionResponse[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [selected, setSelected] = useState<ExecutionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadExecutions() {
    try {
      setLoading(true);
      setError(null);

      const data = await getExecutions(100, 0);
      setExecutions(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load executions."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadExecutions();
  }, []);

  async function openExecution(execution: ExecutionResponse) {
    setSelected(execution);

    try {
      setDetailLoading(true);
      const details = await getExecution(execution.id);
      setSelected(details);
    } catch {
      // Keep the record from the list if detail retrieval fails.
    } finally {
      setDetailLoading(false);
    }
  }

  const filteredExecutions = useMemo(() => {
    return executions.filter((execution) => {
      const query = search.toLowerCase();

      const matchesSearch =
        execution.id.toLowerCase().includes(query) ||
        execution.agent_id.toLowerCase().includes(query) ||
        (execution.external_execution_id || "").toLowerCase().includes(query);

      const matchesStatus =
        statusFilter === "All" || execution.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [executions, search, statusFilter]);

  const counts = {
    total: executions.length,
    running: executions.filter((e) => e.status === "running").length,
    completed: executions.filter((e) => e.status === "completed").length,
    failed: executions.filter((e) => e.status === "failed").length,
  };

  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-white">Executions</h1>
            <p className="mt-1 text-sm text-slate-400">
              Monitor and investigate individual agent executions.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-300">
              Live backend data
            </span>

            <button
              onClick={() => void loadExecutions()}
              disabled={loading}
              className="rounded-lg border border-slate-700 p-2 text-slate-400 hover:bg-slate-800 disabled:opacity-50"
              title="Refresh executions"
            >
              <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Total executions" value={counts.total} icon={<Activity size={18} />} />
          <MetricCard label="Running" value={counts.running} icon={<LoaderCircle size={18} />} />
          <MetricCard label="Completed" value={counts.completed} icon={<CheckCircle2 size={18} />} />
          <MetricCard label="Failed" value={counts.failed} icon={<XCircle size={18} />} />
        </div>

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4">
            <p className="text-sm font-medium text-red-400">Unable to load executions</p>
            <p className="mt-1 break-words text-sm text-red-300">{error}</p>
            <button
              onClick={() => void loadExecutions()}
              className="mt-3 text-sm text-red-300 underline"
            >
              Retry
            </button>
          </div>
        )}

        <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">
          <div className="flex flex-col gap-3 border-b border-slate-800 p-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <h2 className="font-semibold text-white">Execution history</h2>
              <p className="mt-1 text-xs text-slate-400">
                {filteredExecutions.length} executions displayed
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <div className="relative min-w-52 flex-1">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search execution or agent ID..."
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 py-2 pl-9 pr-3 text-sm text-white outline-none focus:border-blue-500"
                />
              </div>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-300 outline-none"
              >
                <option value="All">All statuses</option>
                <option value="completed">Completed</option>
                <option value="running">Running</option>
                <option value="failed">Failed</option>
                <option value="queued">Queued</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[850px] text-left text-sm">
              <thead className="bg-slate-950/70 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Execution</th>
                  <th className="px-5 py-3 font-medium">Agent ID</th>
                  <th className="px-5 py-3 font-medium">Session ID</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Started at</th>
                  <th className="px-5 py-3 font-medium">Duration</th>
                  <th></th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-800">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="px-5 py-12 text-center text-slate-400">
                      <LoaderCircle size={20} className="mx-auto mb-2 animate-spin" />
                      Loading executions from backend...
                    </td>
                  </tr>
                ) : filteredExecutions.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-5 py-12 text-center text-slate-500">
                      {error ? "Execution data could not be loaded." : "No executions found."}
                    </td>
                  </tr>
                ) : (
                  filteredExecutions.map((execution) => (
                    <tr
                      key={execution.id}
                      onClick={() => void openExecution(execution)}
                      className="cursor-pointer transition hover:bg-slate-800/50"
                    >
                      <td className="px-5 py-4">
                        <div className="font-mono text-xs text-blue-400">
                          {execution.id.slice(0, 13)}...
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          {execution.external_execution_id || "No external ID"}
                        </div>
                      </td>

                      <td className="px-5 py-4 font-mono text-xs text-slate-300">
                        {execution.agent_id.slice(0, 13)}...
                      </td>

                      <td className="px-5 py-4 font-mono text-xs text-slate-400">
                        {execution.session_id.slice(0, 13)}...
                      </td>

                      <td className="px-5 py-4">
                        <StatusBadge status={execution.status} />
                      </td>

                      <td className="px-5 py-4 text-xs text-slate-400">
                        {formatDate(execution.started_at || execution.created_at)}
                      </td>

                      <td className="px-5 py-4 tabular-nums text-slate-300">
                        {formatDuration(execution.duration_ms)}
                      </td>

                      <td className="px-5 py-4 text-slate-500">
                        <ArrowUpRight size={16} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
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
                  <p className="text-xs uppercase tracking-wider text-slate-500">
                    Execution details
                  </p>
                  <h2 className="mt-1 break-all font-mono text-lg text-white">
                    {selected.id}
                  </h2>
                  <div className="mt-3">
                    <StatusBadge status={selected.status} />
                  </div>
                </div>

                <button
                  onClick={() => setSelected(null)}
                  className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
                >
                  <X size={18} />
                </button>
              </div>

              {detailLoading && (
                <p className="mt-4 text-xs text-slate-500">Refreshing execution details...</p>
              )}

              <div className="mt-7 space-y-5">
                <Detail label="Agent ID" value={selected.agent_id} mono />
                <Detail label="Agent version ID" value={selected.agent_version_id || "Not assigned"} mono />
                <Detail label="Session ID" value={selected.session_id} mono />
                <Detail label="External execution ID" value={selected.external_execution_id || "Not provided"} />
                <Detail label="Created at" value={formatDate(selected.created_at)} />
                <Detail label="Started at" value={formatDate(selected.started_at)} />
                <Detail label="Ended at" value={formatDate(selected.ended_at)} />
                <Detail label="Duration" value={formatDuration(selected.duration_ms)} />
                <Detail label="Updated at" value={formatDate(selected.updated_at)} />

                {selected.error_type && (
                  <Detail label="Error type" value={selected.error_type} />
                )}

                {selected.error_message && (
                  <div>
                    <h3 className="mb-2 text-sm font-medium text-red-400">Error message</h3>
                    <p className="rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-sm leading-6 text-red-300">
                      {selected.error_message}
                    </p>
                  </div>
                )}

                <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                  <h3 className="text-sm font-medium text-slate-300">Telemetry and trace data</h3>
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    Execution metadata is available. Input/output payloads and trace
                    events are not part of this execution response. They will be
                    retrieved from the telemetry API when events are available.
                  </p>
                </div>
              </div>
            </aside>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function MetricCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
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
