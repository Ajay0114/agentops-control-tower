
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchSessions, ApiClientError } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import StatusBadge from "@/components/ui/status-badge";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/ui/states";
import Pagination from "@/components/ui/pagination";
import type { SessionResponse } from "@/lib/types";

const PAGE_SIZE = 20;

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setSessions(null);

    fetchSessions({ limit: PAGE_SIZE, offset })
      .then((data) => {
        if (!cancelled) setSessions(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiClientError ? err.detail : "Failed to load sessions");
      });

    return () => {
      cancelled = true;
    };
  }, [offset]);

  return (
    <div className="space-y-4 p-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Sessions</h1>
        <p className="text-sm text-slate-400">Conversation/request sessions grouping related executions.</p>
      </div>

      {error && <ErrorState message={error} />}
      {!error && sessions === null && <LoadingSkeleton rows={8} />}
      {!error && sessions?.length === 0 && (
        <EmptyState title="No sessions yet" description="Sessions are created automatically when your SDK starts an execution." />
      )}

      {!error && sessions && sessions.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">External session ID</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Environment</th>
                <th className="px-4 py-2">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {sessions.map((session) => (
                <tr key={session.id} className="hover:bg-slate-900/40">
                  <td className="px-4 py-3">
                    <Link href={`/sessions/${session.id}`} className="text-slate-200 hover:text-blue-400">
                      {session.external_session_id}
                    </Link>
                    <div className="font-mono text-xs text-slate-500">{session.id.slice(0, 8)}</div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={session.status} />
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/environments/${session.environment_id}`}
                      className="font-mono text-xs text-blue-400 hover:underline"
                    >
                      {session.environment_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{formatDateTime(session.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!error && sessions !== null && (
        <Pagination offset={offset} limit={PAGE_SIZE} total={null} onPageChange={setOffset} />
      )}
    </div>
  );
}
