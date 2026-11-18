
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Search } from "lucide-react";

import { fetchAgents, ApiClientError } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import StatusBadge from "@/components/ui/status-badge";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/ui/states";
import Pagination from "@/components/ui/pagination";
import type { AgentResponse } from "@/lib/types";

const PAGE_SIZE = 20;

export default function AgentsPage() {
  const searchParams = useSearchParams();
  const environmentId = searchParams.get("environment_id") ?? undefined;

  const [agents, setAgents] = useState<AgentResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setAgents(null);
    setError(null);

    fetchAgents({ limit: PAGE_SIZE, offset, environment_id: environmentId })
      .then((data) => {
        if (!cancelled) setAgents(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiClientError ? err.detail : "Failed to load agents");
      });

    return () => {
      cancelled = true;
    };
  }, [offset, environmentId]);

  const filtered = agents?.filter((agent) =>
    agent.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Agents</h1>
          <p className="text-sm text-slate-400">
            Agents registered in the Agent Registry.
            {environmentId && (
              <>
                {" "}
                <Link href="/agents" className="text-blue-400 hover:underline">
                  Clear environment filter
                </Link>
              </>
            )}
          </p>
        </div>

        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search this page…"
            className="rounded-md border border-slate-700 bg-slate-900 py-1.5 pl-8 pr-3 text-sm text-slate-200 outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={() => setOffset((o) => o)} />}

      {!error && agents === null && <LoadingSkeleton rows={8} />}

      {!error && agents !== null && filtered!.length === 0 && (
        <EmptyState
          title="No agents found"
          description="Register an agent through the Agent Registry API to see it here."
        />
      )}

      {!error && agents !== null && filtered!.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Framework</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Created</th>
                <th className="px-4 py-2">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filtered!.map((agent) => (
                <tr key={agent.id} className="hover:bg-slate-900/40">
                  <td className="px-4 py-3">
                    <Link href={`/agents/${agent.id}`} className="text-slate-200 hover:text-blue-400">
                      {agent.name}
                    </Link>
                    <div className="font-mono text-xs text-slate-500">{agent.id.slice(0, 8)}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{agent.framework ?? "—"}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={agent.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-400">{formatDateTime(agent.created_at)}</td>
                  <td className="px-4 py-3 text-slate-400">{formatDateTime(agent.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!error && agents !== null && (
        <Pagination offset={offset} limit={PAGE_SIZE} total={null} onPageChange={setOffset} />
      )}
    </div>
  );
}
