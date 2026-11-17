
"use client";

import { useMemo, useState } from "react";
import {
  Search,
  Activity,
  Clock3,
  CheckCircle2,
  XCircle,
  Bot,
  Wrench,
  GitBranch,
  ChevronRight,
  X,
  Copy,
  ArrowUpRight,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";

type TraceStatus = "Completed" | "Failed";

type Span = {
  id: string;
  name: string;
  type: "Agent" | "LLM" | "Tool" | "Workflow";
  status: TraceStatus;
  duration: string;
  detail: string;
};

type Trace = {
  id: string;
  executionId: string;
  agent: string;
  status: TraceStatus;
  startedAt: string;
  duration: string;
  spanCount: number;
  spans: Span[];
};

const traces: Trace[] = [
  {
    id: "trace-a81f29c4",
    executionId: "exec-1024",
    agent: "Customer Support Agent",
    status: "Completed",
    startedAt: "Nov 17, 2026 · 10:42:18",
    duration: "4.2s",
    spanCount: 4,
    spans: [
      { id: "span-001", name: "Customer Support Agent", type: "Agent", status: "Completed", duration: "4.2s", detail: "Root agent execution" },
      { id: "span-002", name: "Understand customer request", type: "LLM", status: "Completed", duration: "1.1s", detail: "Intent and request analysis" },
      { id: "span-003", name: "Order Lookup", type: "Tool", status: "Completed", duration: "1.8s", detail: "Retrieved order information" },
      { id: "span-004", name: "Generate response", type: "LLM", status: "Completed", duration: "1.0s", detail: "Generated final customer response" },
    ],
  },
  {
    id: "trace-b72e18d3",
    executionId: "exec-1023",
    agent: "Home Delivery Agent",
    status: "Failed",
    startedAt: "Nov 17, 2026 · 10:39:52",
    duration: "8.7s",
    spanCount: 3,
    spans: [
      { id: "span-101", name: "Home Delivery Agent", type: "Agent", status: "Failed", duration: "8.7s", detail: "Root agent execution" },
      { id: "span-102", name: "Product Availability", type: "Tool", status: "Failed", duration: "5.2s", detail: "Product availability service returned an upstream error" },
      { id: "span-103", name: "Handle tool failure", type: "LLM", status: "Completed", duration: "1.4s", detail: "Generated failure response" },
    ],
  },
  {
    id: "trace-c93d27e1",
    executionId: "exec-1022",
    agent: "Knowledge Assistant",
    status: "Completed",
    startedAt: "Nov 17, 2026 · 10:37:11",
    duration: "12.1s",
    spanCount: 5,
    spans: [
      { id: "span-201", name: "Knowledge Assistant", type: "Agent", status: "Completed", duration: "12.1s", detail: "Root agent execution" },
      { id: "span-202", name: "Classify question", type: "LLM", status: "Completed", duration: "1.8s", detail: "Question classification" },
      { id: "span-203", name: "Search knowledge base", type: "Tool", status: "Completed", duration: "4.1s", detail: "Retrieved relevant documents" },
      { id: "span-204", name: "Evaluate context", type: "LLM", status: "Completed", duration: "2.2s", detail: "Evaluated retrieved context" },
      { id: "span-205", name: "Generate answer", type: "LLM", status: "Completed", duration: "3.0s", detail: "Generated final answer" },
    ],
  },
];

const statusStyles: Record<TraceStatus, string> = {
  Completed: "bg-emerald-500/10 text-emerald-400",
  Failed: "bg-red-500/10 text-red-400",
};

const typeIcons = {
  Agent: <Bot size={15} />,
  LLM: <Activity size={15} />,
  Tool: <Wrench size={15} />,
  Workflow: <GitBranch size={15} />,
};

export default function TracesPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [selected, setSelected] = useState<Trace | null>(null);

  const filtered = useMemo(() => {
    return traces.filter((trace) => {
      const matchesSearch =
        trace.id.toLowerCase().includes(search.toLowerCase()) ||
        trace.executionId.toLowerCase().includes(search.toLowerCase()) ||
        trace.agent.toLowerCase().includes(search.toLowerCase());

      const matchesStatus =
        statusFilter === "All" || trace.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [search, statusFilter]);

  const totalSpans = traces.reduce((sum, trace) => sum + trace.spanCount, 0);
  const failedTraces = traces.filter((trace) => trace.status === "Failed").length;

  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-white">Traces</h1>
            <p className="mt-1 text-sm text-slate-400">
              Explore agent execution paths, spans, tool calls and model operations.
            </p>
          </div>
          <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-300">
            Demo data · Not live
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <MetricCard label="Total traces" value={traces.length} icon={<GitBranch size={18} />} />
          <MetricCard label="Total spans" value={totalSpans} icon={<Activity size={18} />} />
          <MetricCard label="Failed traces" value={failedTraces} icon={<XCircle size={18} />} />
        </div>

        <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">
          <div className="flex flex-col gap-3 border-b border-slate-800 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="font-semibold text-white">Trace explorer</h2>
              <p className="mt-1 text-xs text-slate-400">
                {filtered.length} traces displayed
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <div className="relative min-w-52 flex-1">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search trace, execution, agent..."
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 py-2 pl-9 pr-3 text-sm text-white outline-none focus:border-blue-500"
                />
              </div>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-300 outline-none"
              >
                <option value="All">All statuses</option>
                <option value="Completed">Completed</option>
                <option value="Failed">Failed</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px] text-left text-sm">
              <thead className="bg-slate-950/70 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Trace ID</th>
                  <th className="px-5 py-3 font-medium">Agent</th>
                  <th className="px-5 py-3 font-medium">Execution ID</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Spans</th>
                  <th className="px-5 py-3 font-medium">Duration</th>
                  <th className="px-5 py-3 font-medium">Started at</th>
                  <th></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filtered.map((trace) => (
                  <tr
                    key={trace.id}
                    onClick={() => setSelected(trace)}
                    className="cursor-pointer transition hover:bg-slate-800/50"
                  >
                    <td className="px-5 py-4 font-mono text-xs text-blue-400">{trace.id}</td>
                    <td className="px-5 py-4 font-medium text-slate-200">{trace.agent}</td>
                    <td className="px-5 py-4 font-mono text-xs text-slate-400">{trace.executionId}</td>
                    <td className="px-5 py-4">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusStyles[trace.status]}`}>
                        {trace.status}
                      </span>
                    </td>
                    <td className="px-5 py-4 tabular-nums text-slate-300">{trace.spanCount}</td>
                    <td className="px-5 py-4 tabular-nums text-slate-300">{trace.duration}</td>
                    <td className="px-5 py-4 text-xs text-slate-400">{trace.startedAt}</td>
                    <td className="px-5 py-4 text-slate-500"><ArrowUpRight size={16} /></td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-5 py-12 text-center text-slate-500">
                      No traces match your filters.
                    </td>
                  </tr>
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
              className="h-full w-full max-w-2xl overflow-y-auto border-l border-slate-800 bg-slate-950 p-6 shadow-2xl"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Trace details</p>
                  <h2 className="mt-1 font-mono text-lg text-white">{selected.id}</h2>
                  <p className="mt-2 text-sm text-slate-400">{selected.agent}</p>
                  <span className={`mt-3 inline-flex rounded-full px-2.5 py-1 text-xs ${statusStyles[selected.status]}`}>
                    {selected.status}
                  </span>
                </div>
                <button
                  onClick={() => setSelected(null)}
                  className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="mt-7 grid grid-cols-2 gap-3">
                <InfoCard label="Execution ID" value={selected.executionId} mono />
                <InfoCard label="Duration" value={selected.duration} />
                <InfoCard label="Span count" value={String(selected.spanCount)} />
                <InfoCard label="Started at" value={selected.startedAt} />
              </div>

              <div className="mt-8">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-white">Execution timeline</h3>
                    <p className="mt-1 text-xs text-slate-500">
                      Hierarchical view of operations within this trace
                    </p>
                  </div>
                  <span className="text-xs text-slate-500">{selected.spans.length} spans</span>
                </div>

                <div className="space-y-2">
                  {selected.spans.map((span, index) => (
                    <div key={span.id} className="relative">
                      {index > 0 && (
                        <div className="absolute -top-2 left-5 h-2 border-l border-slate-700" />
                      )}
                      <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-800 text-blue-400">
                            {typeIcons[span.type]}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-slate-200">{span.name}</p>
                            <p className="mt-1 text-xs text-slate-500">{span.type} · {span.id}</p>
                          </div>
                          <div className="text-right">
                            {span.status === "Completed" ? (
                              <CheckCircle2 size={15} className="ml-auto text-emerald-400" />
                            ) : (
                              <XCircle size={15} className="ml-auto text-red-400" />
                            )}
                            <p className="mt-1 text-xs tabular-nums text-slate-400">{span.duration}</p>
                          </div>
                        </div>
                        <p className="ml-12 mt-2 text-xs leading-5 text-slate-400">{span.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-7 rounded-lg border border-slate-800 bg-slate-900 p-4">
                <h3 className="text-sm font-medium text-slate-200">Trace correlation</h3>
                <p className="mt-2 text-xs text-slate-500">
                  This trace is associated with execution {selected.executionId}.
                  In the connected version, spans will be correlated using trace_id,
                  span_id and parent_span_id.
                </p>
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
      <div className="mt-3 text-3xl font-semibold tabular-nums text-white">{value}</div>
    </div>
  );
}

function InfoCard({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-2 break-all text-sm text-slate-200 ${mono ? "font-mono text-xs" : ""}`}>
        {value}
      </p>
    </div>
  );
}
