
"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { fetchSession, fetchExecutions, ApiClientError } from "@/lib/api/client";
import { formatDateTime, formatDuration } from "@/lib/format";
import StatusBadge from "@/components/ui/status-badge";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/ui/states";
import type { ExecutionResponse, SessionResponse } from "@/lib/types";

export default function SessionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const [session, setSession] = useState<SessionResponse | null>(null);
  const [executions, setExecutions] = useState<ExecutionResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchSession(id), fetchExecutions({ session_id: id, limit: 50 })])
      .then(([sessionData, executionData]) => {
        setSession(sessionData);
        setExecutions(executionData.items);
      })
      .catch((err) =>
        setError(
          err instanceof ApiClientError
            ? err.status === 404
              ? "Session not found"
              : err.detail
            : "Failed to load session"
        )
      );
  }, [id]);

  if (error) return <div className="p-6"><ErrorState message={error} /></div>;
  if (!session) return <div className="p-6"><LoadingSkeleton rows={6} /></div>;

  return (
    <div className="space-y-6 p-6">
      <Link href="/sessions" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={14} /> Back to sessions
      </Link>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">{session.external_session_id}</h1>
          <p className="font-mono text-xs text-slate-500">{session.id}</p>
        </div>
        <StatusBadge status={session.status} />
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-lg border border-slate-800 bg-slate-900/60 p-4 md:grid-cols-4">
        <div>
          <div className="text-xs uppercase text-slate-500">Environment</div>
          <Link href={`/environments/${session.environment_id}`} className="mt-1 block font-mono text-xs text-blue-400 hover:underline">
            {session.environment_id.slice(0, 8)}
          </Link>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Started</div>
          <div className="mt-1 text-slate-200">{formatDateTime(session.started_at)}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Ended</div>
          <div className="mt-1 text-slate-200">{formatDateTime(session.ended_at)}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Created</div>
          <div className="mt-1 text-slate-200">{formatDateTime(session.created_at)}</div>
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-slate-300">Executions in this session</h2>

        {executions === null ? (
          <LoadingSkeleton rows={3} />
        ) : executions.length === 0 ? (
          <EmptyState title="No executions in this session yet" />
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2">Execution</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Duration</th>
                  <th className="px-4 py-2">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {executions.map((execution) => (
                  <tr key={execution.id} className="hover:bg-slate-900/40">
                    <td className="px-4 py-3">
                      <Link href={`/executions/${execution.id}`} className="font-mono text-xs text-blue-400 hover:underline">
                        {execution.id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={execution.status} /></td>
                    <td className="px-4 py-3 text-slate-400">{formatDuration(execution.duration_ms)}</td>
                    <td className="px-4 py-3 text-slate-400">{formatDateTime(execution.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
