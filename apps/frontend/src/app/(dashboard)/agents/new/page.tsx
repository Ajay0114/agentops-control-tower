
"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { createAgent, fetchEnvironments, ApiClientError } from "@/lib/api/client";
import { LoadingSkeleton } from "@/components/ui/states";
import type { EnvironmentResponse } from "@/lib/types";

function slugify(name: string): string {
  return (
    name
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "agent"
  );
}

export default function NewAgentPage() {
  const router = useRouter();

  const [environments, setEnvironments] = useState<EnvironmentResponse[] | null>(null);
  const [environmentsError, setEnvironmentsError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [framework, setFramework] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchEnvironments({ limit: 100 })
      .then((data) => {
        setEnvironments(data);
        if (data.length > 0) setEnvironmentId(data[0].id);
      })
      .catch((err) =>
        setEnvironmentsError(err instanceof ApiClientError ? err.detail : "Failed to load environments")
      );
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (!name.trim()) {
      setError("Name is required.");
      return;
    }

    if (!environmentId) {
      setError("Choose an environment - create one from Settings if none are listed.");
      return;
    }

    setError(null);
    setSubmitting(true);

    try {
      const agent = await createAgent({
        environmentId,
        name: name.trim(),
        slug: slugify(name),
        framework: framework.trim() || undefined,
        description: description.trim() || undefined,
      });

      router.push(`/agents/${agent.id}`);
      router.refresh();
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(
          err.status === 409
            ? "An agent with this name already exists in this environment."
            : err.status === 404
              ? "That environment could not be found."
              : err.detail
        );
      } else {
        setError("Failed to register agent. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6 p-6">
      <Link href="/agents" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={14} /> Back to agents
      </Link>

      <div>
        <h1 className="text-xl font-semibold text-slate-100">Register agent</h1>
        <p className="text-sm text-slate-400">Adds a new agent to the Agent Registry.</p>
      </div>

      <form
        onSubmit={handleSubmit}
        noValidate
        className="max-w-lg space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-5"
      >
        <div>
          <label htmlFor="agent-name" className="mb-1 block text-sm text-slate-300">
            Name
          </label>
          <input
            id="agent-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Support Bot"
            autoFocus
            required
            className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label htmlFor="agent-environment" className="mb-1 block text-sm text-slate-300">
            Environment
          </label>

          {environmentsError && <p className="text-sm text-red-400">{environmentsError}</p>}

          {!environmentsError && environments === null && <LoadingSkeleton rows={1} />}

          {!environmentsError && environments !== null && environments.length === 0 && (
            <p className="text-sm text-slate-500">
              No environments yet -{" "}
              <Link href="/environments" className="text-blue-400 hover:underline">
                create one first
              </Link>
              .
            </p>
          )}

          {!environmentsError && environments !== null && environments.length > 0 && (
            <select
              id="agent-environment"
              value={environmentId}
              onChange={(event) => setEnvironmentId(event.target.value)}
              required
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-blue-500"
            >
              {environments.map((environment) => (
                <option key={environment.id} value={environment.id}>
                  {environment.name} ({environment.slug})
                </option>
              ))}
            </select>
          )}
        </div>

        <div>
          <label htmlFor="agent-framework" className="mb-1 block text-sm text-slate-300">
            Framework <span className="text-slate-500">(optional)</span>
          </label>
          <input
            id="agent-framework"
            value={framework}
            onChange={(event) => setFramework(event.target.value)}
            placeholder="e.g. langgraph"
            className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label htmlFor="agent-description" className="mb-1 block text-sm text-slate-300">
            Description <span className="text-slate-500">(optional)</span>
          </label>
          <textarea
            id="agent-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={3}
            className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-blue-500"
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-400">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting || environments === null || environments.length === 0}
          className="w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-50"
        >
          {submitting ? "Registering…" : "Register agent"}
        </button>
      </form>
    </div>
  );
}
