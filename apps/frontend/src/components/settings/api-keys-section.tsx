
"use client";

import { useEffect, useState } from "react";
import { Check, Copy, KeyRound, Plus, Trash2 } from "lucide-react";

import {
  createIntegrationApiKey,
  fetchIntegrationApiKeys,
  revokeIntegrationApiKey,
  ApiClientError,
} from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import StatusBadge from "@/components/ui/status-badge";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/ui/states";
import SdkOnboardingGuide from "./sdk-onboarding-guide";
import type { IntegrationApiKey } from "@/lib/types";

export default function ApiKeysSection({ backendUrl }: { backendUrl: string }) {
  const [keys, setKeys] = useState<IntegrationApiKey[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newKeyName, setNewKeyName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [justCreatedKey, setJustCreatedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmingRevokeId, setConfirmingRevokeId] = useState<string | null>(null);

  function load() {
    setError(null);
    fetchIntegrationApiKeys()
      .then(setKeys)
      .catch((err) => setError(err instanceof ApiClientError ? err.detail : "Failed to load API keys"));
  }

  useEffect(load, []);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    if (!newKeyName.trim()) return;

    setCreating(true);
    setCreateError(null);

    try {
      const result = await createIntegrationApiKey({ name: newKeyName.trim() });
      setJustCreatedKey(result.raw_key);
      setNewKeyName("");
      load();
    } catch (err) {
      setCreateError(err instanceof ApiClientError ? err.detail : "Failed to create key");
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(id: string) {
    try {
      await revokeIntegrationApiKey(id);
      setConfirmingRevokeId(null);
      load();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.detail : "Failed to revoke key");
    }
  }

  async function copyKey() {
    if (!justCreatedKey) return;
    try {
      await navigator.clipboard.writeText(justCreatedKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be denied by the browser - the key is still
      // selectable/visible in the box below, so this is a soft failure.
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-sm font-medium text-slate-300">API Keys</h2>
        <p className="text-xs text-slate-500">
          Integration keys for the Python SDK and external agents. Separate from, and never as
          powerful to view as, the internal key this dashboard uses for its own requests - that
          one is never shown here.
        </p>
      </div>

      {justCreatedKey && (
        <div className="space-y-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
          <p className="text-sm font-medium text-amber-300">
            Copy this key now - it cannot be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded bg-slate-950 px-3 py-2 text-xs text-slate-200">
              {justCreatedKey}
            </code>
            <button
              onClick={copyKey}
              className="flex items-center gap-1 rounded-md border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:bg-slate-800"
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>

          <details className="text-xs text-slate-400">
            <summary className="cursor-pointer text-slate-300">
              How do I use this with the Python SDK?
            </summary>
            <div className="mt-3">
              <SdkOnboardingGuide backendUrl={backendUrl} />
            </div>
          </details>

          <button
            onClick={() => setJustCreatedKey(null)}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Dismiss
          </button>
        </div>
      )}

      <form onSubmit={handleCreate} className="flex items-end gap-2">
        <div className="flex-1">
          <label htmlFor="new-key-name" className="mb-1 block text-xs text-slate-400">
            New key name
          </label>
          <input
            id="new-key-name"
            value={newKeyName}
            onChange={(event) => setNewKeyName(event.target.value)}
            placeholder="e.g. CI pipeline"
            className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 outline-none focus:border-blue-500"
          />
        </div>
        <button
          type="submit"
          disabled={creating || !newKeyName.trim()}
          className="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
        >
          <Plus size={14} /> {creating ? "Creating…" : "Create key"}
        </button>
      </form>
      {createError && <p className="text-xs text-red-400">{createError}</p>}

      {error && <ErrorState message={error} onRetry={load} />}

      {!error && keys === null && <LoadingSkeleton rows={3} />}

      {!error && keys?.length === 0 && (
        <EmptyState
          title="No integration keys yet"
          description="Create one above to start sending telemetry from the Python SDK."
          icon={<KeyRound size={28} className="text-slate-500" />}
        />
      )}

      {!error && keys && keys.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Prefix</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Created</th>
                <th className="px-4 py-2">Last used</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {keys.map((key) => (
                <tr key={key.id}>
                  <td className="px-4 py-3 text-slate-200">{key.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400">{key.key_prefix}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={key.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-400">{formatDateTime(key.created_at)}</td>
                  <td className="px-4 py-3 text-slate-400">{formatDateTime(key.last_used_at)}</td>
                  <td className="px-4 py-3 text-right">
                    {key.status === "active" &&
                      (confirmingRevokeId === key.id ? (
                        <span className="flex items-center justify-end gap-2">
                          <span className="text-xs text-slate-400">Revoke this key?</span>
                          <button
                            onClick={() => handleRevoke(key.id)}
                            className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-500"
                          >
                            Confirm
                          </button>
                          <button
                            onClick={() => setConfirmingRevokeId(null)}
                            className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
                          >
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <button
                          onClick={() => setConfirmingRevokeId(key.id)}
                          className="flex items-center gap-1 rounded border border-slate-700 px-2 py-1 text-xs text-red-300 hover:bg-red-500/10"
                          aria-label={`Revoke ${key.name}`}
                        >
                          <Trash2 size={12} /> Revoke
                        </button>
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
