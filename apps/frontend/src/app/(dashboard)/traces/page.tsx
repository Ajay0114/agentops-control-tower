
"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { GitBranch } from "lucide-react";

export default function TracesLandingPage() {
  const router = useRouter();
  const [traceId, setTraceId] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (traceId.trim()) {
      router.push(`/traces/${traceId.trim()}`);
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Traces</h1>
        <p className="text-sm text-slate-400">
          Inspect the span hierarchy for one trace. There is no standalone "list all traces"
          endpoint today, since a trace is always one execution's own nested spans - open a
          trace from an execution's detail page, or paste a trace ID below.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex max-w-lg items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <GitBranch size={18} className="text-slate-500" />
        <input
          value={traceId}
          onChange={(event) => setTraceId(event.target.value)}
          placeholder="Paste a trace ID (32 hex characters)"
          className="flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-blue-500"
        />
        <button
          type="submit"
          className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500"
        >
          Open
        </button>
      </form>
    </div>
  );
}
