
"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { fetchEnvironment, ApiClientError } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { ErrorState, LoadingSkeleton } from "@/components/ui/states";
import type { EnvironmentResponse } from "@/lib/types";

export default function EnvironmentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [environment, setEnvironment] = useState<EnvironmentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchEnvironment(id)
      .then(setEnvironment)
      .catch((err) =>
        setError(
          err instanceof ApiClientError
            ? err.status === 404
              ? "Environment not found"
              : err.detail
            : "Failed to load environment"
        )
      );
  }, [id]);

  if (error) return <div className="p-6"><ErrorState message={error} /></div>;
  if (!environment) return <div className="p-6"><LoadingSkeleton rows={4} /></div>;

  return (
    <div className="space-y-6 p-6">
      <Link href="/environments" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={14} /> Back to environments
      </Link>

      <div>
        <h1 className="text-xl font-semibold text-slate-100">{environment.name}</h1>
        <p className="font-mono text-xs text-slate-500">{environment.id}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-lg border border-slate-800 bg-slate-900/60 p-4 md:grid-cols-3">
        <div>
          <div className="text-xs uppercase text-slate-500">Slug</div>
          <div className="mt-1 text-slate-200">{environment.slug}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Project</div>
          <div className="mt-1 font-mono text-xs text-slate-300">{environment.project_id.slice(0, 8)}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Created</div>
          <div className="mt-1 text-slate-200">{formatDateTime(environment.created_at)}</div>
        </div>
      </div>

      {environment.description && (
        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-300">
          {environment.description}
        </div>
      )}

      <Link
        href={`/agents?environment_id=${environment.id}`}
        className="inline-block text-sm text-blue-400 hover:underline"
      >
        View agents in this environment →
      </Link>
    </div>
  );
}
