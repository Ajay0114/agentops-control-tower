
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchEnvironments, ApiClientError } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/ui/states";
import type { EnvironmentResponse } from "@/lib/types";

export default function EnvironmentsPage() {
  const [environments, setEnvironments] = useState<EnvironmentResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchEnvironments({ limit: 100 })
      .then(setEnvironments)
      .catch((err) =>
        setError(err instanceof ApiClientError ? err.detail : "Failed to load environments")
      );
  }, []);

  return (
    <div className="space-y-4 p-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Environments</h1>
        <p className="text-sm text-slate-400">Environments registered under your project(s).</p>
      </div>

      {error && <ErrorState message={error} />}
      {!error && environments === null && <LoadingSkeleton rows={4} />}
      {!error && environments?.length === 0 && (
        <EmptyState title="No environments found" description="Create one through the Environments API." />
      )}

      {!error && environments && environments.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Slug</th>
                <th className="px-4 py-2">Description</th>
                <th className="px-4 py-2">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {environments.map((environment) => (
                <tr key={environment.id} className="hover:bg-slate-900/40">
                  <td className="px-4 py-3">
                    <Link
                      href={`/environments/${environment.id}`}
                      className="text-slate-200 hover:text-blue-400"
                    >
                      {environment.name}
                    </Link>
                    <div className="font-mono text-xs text-slate-500">{environment.id.slice(0, 8)}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{environment.slug}</td>
                  <td className="px-4 py-3 text-slate-400">{environment.description ?? "—"}</td>
                  <td className="px-4 py-3 text-slate-400">{formatDateTime(environment.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
