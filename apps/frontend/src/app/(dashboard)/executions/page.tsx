
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";

import { fetchExecutions, fetchEnvironments, ApiClientError, type ExecutionFilters } from "@/lib/api/client";
import { formatDateTime, formatDuration } from "@/lib/format";
import StatusBadge from "@/components/ui/status-badge";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/ui/states";
import Pagination from "@/components/ui/pagination";
import type { EnvironmentResponse, ExecutionResponse } from "@/lib/types";

const PAGE_SIZE = 25;
const STATUS_OPTIONS = ["queued", "running", "completed", "failed", "cancelled"];

export default function ExecutionsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const agentId = searchParams.get("agent_id") ?? "";
  const status = searchParams.get("status") ?? "";
  const environmentId = searchParams.get("environment_id") ?? "";
  const sessionId = searchParams.get("session_id") ?? "";
  const startedAfter = searchParams.get("started_after") ?? "";
  const startedBefore = searchParams.get("started_before") ?? "";
  const executionIdSearch = searchParams.get("q") ?? "";

  const [offset, setOffset] = useState(0);
  const [result, setResult] = useState<{ items: ExecutionResponse[]; total: number | null } | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const [environments, setEnvironments] = useState<EnvironmentResponse[]>([]);

  useEffect(() => {
    fetchEnvironments({ limit: 100 }).then(setEnvironments).catch(() => setEnvironments([]));
  }, []);

  useEffect(() => {
    setOffset(0);
  }, [agentId, status, environmentId, sessionId, startedAfter, startedBefore, executionIdSearch]);

  useEffect(() => {
    let cancelled = false;
    setResult(null);
    setError(null);

    const filters: ExecutionFilters = {
      limit: PAGE_SIZE,
      offset,
      agent_id: agentId || undefined,
      status: status || undefined,
      environment_id: environmentId || undefined,
      session_id: sessionId || undefined,
      started_after: startedAfter ? new Date(startedAfter).toISOString() : undefined,
      started_before: startedBefore ? new Date(startedBefore).toISOString() : undefined,
    };

    // A full UUID is treated as an exact-id lookup; anything else is
    // ignored server-side (see executions.py's execution_id param), so a
    // partial/invalid value simply falls back to the unfiltered list.
    const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      executionIdSearch
    );
    if (isUuid) {
      filters.execution_id = executionIdSearch;
    }

    fetchExecutions(filters)
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiClientError ? err.detail : "Failed to load executions");
      });

    return () => {
      cancelled = true;
    };
  }, [offset, agentId, status, environmentId, sessionId, startedAfter, startedBefore, executionIdSearch]);

  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(searchParams.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    router.push(`/executions?${next.toString()}`);
  }

  return (
    <div className="space-y-4 p-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Executions</h1>
        <p className="text-sm text-slate-400">All agent executions across your scope.</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          value={executionIdSearch}
          onChange={(event) => updateParam("q", event.target.value)}
          placeholder="Search by execution ID (UUID)"
          className="w-64 rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-blue-500"
        />

        <select
          value={status}
          onChange={(event) => updateParam("status", event.target.value)}
          className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>

        <select
          value={environmentId}
          onChange={(event) => updateParam("environment_id", event.target.value)}
          className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200"
        >
          <option value="">All environments</option>
          {environments.map((environment) => (
            <option key={environment.id} value={environment.id}>
              {environment.name}
            </option>
          ))}
        </select>

        <input
          value={sessionId}
          onChange={(event) => updateParam("session_id", event.target.value)}
          placeholder="Session ID"
          className="w-40 rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-blue-500"
        />

        <label className="flex items-center gap-1.5 text-xs text-slate-400">
          From
          <input
            type="date"
            value={startedAfter}
            onChange={(event) => updateParam("started_after", event.target.value)}
            className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-200"
          />
        </label>

        <label className="flex items-center gap-1.5 text-xs text-slate-400">
          To
          <input
            type="date"
            value={startedBefore}
            onChange={(event) => updateParam("started_before", event.target.value)}
            className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-200"
          />
        </label>

        {agentId && (
          <button
            onClick={() => updateParam("agent_id", "")}
            className="rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            Agent filter: {agentId.slice(0, 8)} ✕
          </button>
        )}
      </div>

      {error && <ErrorState message={error} />}
      {!error && result === null && <LoadingSkeleton rows={10} />}
      {!error && result?.items.length === 0 && (
        <EmptyState title="No executions match these filters" />
      )}

      {!error && result && result.items.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">Execution</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Session</th>
                <th className="px-4 py-2">Duration</th>
                <th className="px-4 py-2">Started</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {result.items.map((execution) => (
                <tr key={execution.id} className="hover:bg-slate-900/40">
                  <td className="px-4 py-3">
                    <Link href={`/executions/${execution.id}`} className="font-mono text-xs text-blue-400 hover:underline">
                      {execution.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={execution.status} />
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/sessions/${execution.session_id}`} className="font-mono text-xs text-slate-400 hover:text-blue-400">
                      {execution.session_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{formatDuration(execution.duration_ms)}</td>
                  <td className="px-4 py-3 text-slate-400">{formatDateTime(execution.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!error && result && (
        <Pagination offset={offset} limit={PAGE_SIZE} total={result.total} onPageChange={setOffset} />
      )}
    </div>
  );
}
