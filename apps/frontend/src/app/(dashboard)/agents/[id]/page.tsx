
"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { fetchAgent, fetchAgentVersions, ApiClientError } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import StatusBadge from "@/components/ui/status-badge";
import { ErrorState, LoadingSkeleton, EmptyState } from "@/components/ui/states";
import type { AgentResponse, AgentVersionResponse } from "@/lib/types";

export default function AgentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const [agent, setAgent] = useState<AgentResponse | null>(null);
  const [versions, setVersions] = useState<AgentVersionResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([fetchAgent(id), fetchAgentVersions(id, { limit: 50 })])
      .then(([agentData, versionData]) => {
        if (cancelled) return;
        setAgent(agentData);
        setVersions(versionData);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err instanceof ApiClientError
            ? err.status === 404
              ? "Agent not found"
              : err.detail
            : "Failed to load agent"
        );
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) {
    return (
      <div className="p-6">
        <ErrorState message={error} />
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <Link href="/agents" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={14} /> Back to agents
      </Link>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">{agent.name}</h1>
          <p className="font-mono text-xs text-slate-500">{agent.id}</p>
        </div>
        <StatusBadge status={agent.status} />
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-lg border border-slate-800 bg-slate-900/60 p-4 md:grid-cols-4">
        <div>
          <div className="text-xs uppercase text-slate-500">Framework</div>
          <div className="mt-1 text-slate-200">{agent.framework ?? "—"}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Environment</div>
          <Link
            href={`/environments/${agent.environment_id}`}
            className="mt-1 block font-mono text-xs text-blue-400 hover:underline"
          >
            {agent.environment_id.slice(0, 8)}
          </Link>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Created</div>
          <div className="mt-1 text-slate-200">{formatDateTime(agent.created_at)}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Updated</div>
          <div className="mt-1 text-slate-200">{formatDateTime(agent.updated_at)}</div>
        </div>
      </div>

      {agent.description && (
        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-300">
          {agent.description}
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium text-slate-300">Version history</h2>
          <Link
            href={`/executions?agent_id=${agent.id}`}
            className="text-xs text-blue-400 hover:underline"
          >
            View executions for this agent
          </Link>
        </div>

        {versions === null ? (
          <LoadingSkeleton rows={3} />
        ) : versions.length === 0 ? (
          <EmptyState title="No versions yet" description="Register a version through the Agent Registry API." />
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2">Version</th>
                  <th className="px-4 py-2">Deployment status</th>
                  <th className="px-4 py-2">Deployed</th>
                  <th className="px-4 py-2">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {versions.map((version) => (
                  <tr key={version.id}>
                    <td className="px-4 py-3 font-medium text-slate-200">{version.version}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={version.deployment_status} />
                    </td>
                    <td className="px-4 py-3 text-slate-400">{formatDateTime(version.deployed_at)}</td>
                    <td className="px-4 py-3 text-slate-400">{formatDateTime(version.created_at)}</td>
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
