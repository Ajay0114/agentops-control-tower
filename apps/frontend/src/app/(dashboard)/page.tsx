import Link from "next/link";

import { backendRequest, BackendError } from "@/lib/server/backend";
import { formatDuration, formatPercent, formatRelativeOrDate, formatTokenCount } from "@/lib/format";
import StatusBadge from "@/components/ui/status-badge";
import { EmptyState } from "@/components/ui/states";
import type { DashboardOverview } from "@/lib/types";

export const dynamic = "force-dynamic";

function MetricCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-100">{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export default async function OverviewPage() {
  let overview: DashboardOverview;

  try {
    const { data } = await backendRequest<DashboardOverview>("/api/v1/dashboard/overview");
    overview = data;
  } catch (error) {
    if (error instanceof BackendError) {
      return (
        <div className="p-6">
          <EmptyState
            title="Could not load the overview"
            description={`The backend returned HTTP ${error.status}.`}
          />
        </div>
      );
    }
    throw error;
  }

  const maxTrend = Math.max(1, ...overview.execution_trend.map((point) => point.count));

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Overview</h1>
        <p className="text-sm text-slate-400">Operational summary across registered agents.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <MetricCard label="Total executions" value={String(overview.total_executions)} />
        <MetricCard label="Running" value={String(overview.running_executions)} />
        <MetricCard label="Completed" value={String(overview.completed_executions)} />
        <MetricCard label="Failed" value={String(overview.failed_executions)} />
        <MetricCard label="Success rate" value={formatPercent(overview.success_rate)} />
        <MetricCard label="Registered agents" value={String(overview.total_agents)} />
        <MetricCard
          label="Tokens used"
          value={formatTokenCount(overview.total_tokens_used)}
          hint={overview.total_tokens_used === null ? "No LLM telemetry reported yet" : undefined}
        />
        <MetricCard label="Queued / Cancelled" value={`${overview.queued_executions} / ${overview.cancelled_executions}`} />
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <h2 className="mb-4 text-sm font-medium text-slate-300">Executions, last 7 days</h2>
        <div className="flex h-32 items-end gap-3">
          {overview.execution_trend.map((point) => (
            <div key={point.date} className="flex flex-1 flex-col items-center gap-2">
              <div
                className="w-full rounded-t bg-blue-500/60"
                style={{ height: `${Math.max(4, (point.count / maxTrend) * 100)}%` }}
                title={`${point.count} executions`}
              />
              <span className="text-[10px] text-slate-500">
                {new Date(point.date).toLocaleDateString(undefined, { weekday: "short" })}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-300">Recent executions</h2>
            <Link href="/executions" className="text-xs text-blue-400 hover:underline">
              View all
            </Link>
          </div>

          {overview.recent_executions.length === 0 ? (
            <EmptyState title="No executions yet" description="Executions will appear here once your agents start running." />
          ) : (
            <ul className="divide-y divide-slate-800">
              {overview.recent_executions.map((execution) => (
                <li key={execution.id} className="flex items-center justify-between py-2 text-sm">
                  <Link href={`/executions/${execution.id}`} className="text-slate-300 hover:text-blue-400">
                    {execution.id.slice(0, 8)}
                  </Link>
                  <span className="text-slate-500">{formatDuration(execution.duration_ms)}</span>
                  <StatusBadge status={execution.status} />
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-300">Recent agent activity</h2>
            <Link href="/agents" className="text-xs text-blue-400 hover:underline">
              View all
            </Link>
          </div>

          {overview.recent_agents.length === 0 ? (
            <EmptyState title="No agents registered" description="Register an agent through the Agent Registry API to see it here." />
          ) : (
            <ul className="divide-y divide-slate-800">
              {overview.recent_agents.map((agent) => (
                <li key={agent.id} className="flex items-center justify-between py-2 text-sm">
                  <Link href={`/agents/${agent.id}`} className="text-slate-300 hover:text-blue-400">
                    {agent.name}
                  </Link>
                  <span className="text-slate-500">{formatRelativeOrDate(agent.updated_at)}</span>
                  <StatusBadge status={agent.status} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
