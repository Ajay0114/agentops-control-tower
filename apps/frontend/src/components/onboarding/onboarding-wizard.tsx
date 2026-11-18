
"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Check, Command, FolderTree, KeyRound, Layers } from "lucide-react";

import { createEnvironment, createProject, ApiClientError } from "@/lib/api/client";
import ApiKeysSection from "@/components/settings/api-keys-section";
import type { Project } from "@/lib/types";

type Step = "project" | "environment" | "api-key";

const STEPS: { key: Step; label: string; icon: typeof FolderTree }[] = [
  { key: "project", label: "Project", icon: Layers },
  { key: "environment", label: "Environment", icon: FolderTree },
  { key: "api-key", label: "Integration key", icon: KeyRound },
];

function slugify(name: string): string {
  return (
    name
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "default"
  );
}

function StepHeader({ current }: { current: Step }) {
  const currentIndex = STEPS.findIndex((step) => step.key === current);

  return (
    <div className="mb-8 flex items-center justify-center gap-3">
      {STEPS.map((step, index) => {
        const Icon = step.icon;
        const done = index < currentIndex;
        const active = index === currentIndex;

        return (
          <div key={step.key} className="flex items-center gap-3">
            <div
              className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs ${
                active
                  ? "border-blue-500 bg-blue-500/10 text-blue-300"
                  : done
                    ? "border-emerald-600/40 bg-emerald-500/5 text-emerald-300"
                    : "border-slate-800 text-slate-500"
              }`}
            >
              {done ? <Check size={14} /> : <Icon size={14} />}
              {step.label}
            </div>
            {index < STEPS.length - 1 && <div className="h-px w-6 bg-slate-800" />}
          </div>
        );
      })}
    </div>
  );
}

export default function OnboardingWizard({
  organizationName,
  backendUrl,
}: {
  organizationName: string;
  backendUrl: string;
}) {
  const router = useRouter();
  const [step, setStep] = useState<Step>("project");
  const [project, setProject] = useState<Project | null>(null);

  const [projectName, setProjectName] = useState("Default");
  const [environmentName, setEnvironmentName] = useState("Production");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreateProject(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const created = await createProject(projectName.trim() || "Default");
      setProject(created);
      setStep("environment");
    } catch (err) {
      setError(err instanceof ApiClientError ? err.detail : "Failed to create project");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreateEnvironment(event: FormEvent) {
    event.preventDefault();
    if (!project) return;

    setError(null);
    setSubmitting(true);

    try {
      const name = environmentName.trim() || "Production";
      await createEnvironment({ projectId: project.id, name, slug: slugify(name) });
      setStep("api-key");
    } catch (err) {
      setError(err instanceof ApiClientError ? err.detail : "Failed to create environment");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#090e19] px-4 py-12">
      <div className="mx-auto w-full max-w-lg">
        <div className="mb-6 flex items-center justify-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-lg bg-[#334e9b] text-white">
            <Command size={20} />
          </div>
          <div>
            <div className="font-semibold text-slate-100">{organizationName}</div>
            <div className="text-xs tracking-wide text-slate-500">GETTING STARTED</div>
          </div>
        </div>

        <StepHeader current={step} />

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
          {step === "project" && (
            <form onSubmit={handleCreateProject} className="space-y-4">
              <div>
                <h2 className="text-sm font-medium text-slate-200">Create your first project</h2>
                <p className="mt-1 text-xs text-slate-500">
                  A project groups the environments, agents and API keys for one piece of work -
                  you can create more later from Settings.
                </p>
              </div>

              <div>
                <label htmlFor="project-name" className="mb-1 block text-sm text-slate-300">
                  Project name
                </label>
                <input
                  id="project-name"
                  value={projectName}
                  onChange={(event) => setProjectName(event.target.value)}
                  autoFocus
                  required
                  className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-blue-500"
                />
              </div>

              {error && <p className="text-sm text-red-400">{error}</p>}

              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-50"
              >
                {submitting ? "Creating…" : "Continue"}
              </button>
            </form>
          )}

          {step === "environment" && (
            <form onSubmit={handleCreateEnvironment} className="space-y-4">
              <div>
                <h2 className="text-sm font-medium text-slate-200">Create a development environment</h2>
                <p className="mt-1 text-xs text-slate-500">
                  Environments separate, for example, development from production telemetry
                  within &quot;{project?.name}&quot;.
                </p>
              </div>

              <div>
                <label htmlFor="environment-name" className="mb-1 block text-sm text-slate-300">
                  Environment name
                </label>
                <input
                  id="environment-name"
                  value={environmentName}
                  onChange={(event) => setEnvironmentName(event.target.value)}
                  autoFocus
                  required
                  className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-blue-500"
                />
              </div>

              {error && <p className="text-sm text-red-400">{error}</p>}

              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-50"
              >
                {submitting ? "Creating…" : "Continue"}
              </button>
            </form>
          )}

          {step === "api-key" && (
            <div className="space-y-5">
              <div>
                <h2 className="text-sm font-medium text-slate-200">
                  Generate an integration key for the Python SDK
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  This key is what your agent uses to send telemetry - it is shown only once below.
                </p>
              </div>

              <ApiKeysSection backendUrl={backendUrl} />

              <button
                onClick={() => {
                  router.push("/");
                  router.refresh();
                }}
                className="w-full rounded-md border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800"
              >
                Go to dashboard
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
