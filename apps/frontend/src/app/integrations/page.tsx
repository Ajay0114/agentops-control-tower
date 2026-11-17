
"use client";

import { useState } from "react";
import {
  Bot,
  Workflow,
  Cloud,
  Code2,
  Activity,
  Plug,
  CheckCircle2,
  Circle,
  ArrowUpRight,
  Copy,
  X,
  Terminal,
  ShieldCheck,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";

type Integration = {
  id: string;
  name: string;
  category: string;
  description: string;
  icon: React.ReactNode;
  status: "Available" | "Planned";
  method: string;
  setup: string[];
};

const integrations: Integration[] = [
  {
    id: "custom-python",
    name: "Custom Python Agents",
    category: "Python SDK",
    description: "Instrument existing Python agents and capture executions, model calls, tool calls and errors.",
    icon: <Code2 size={24} />,
    status: "Available",
    method: "Python SDK / REST API",
    setup: [
      "Create or select an AgentOps agent registration.",
      "Configure the AgentOps API endpoint and credentials.",
      "Install the AgentOps Python SDK when SDK instrumentation is ready, or send telemetry using the REST API.",
      "Emit execution lifecycle and telemetry events.",
    ],
  },
  {
    id: "kore-artemis",
    name: "Kore.ai Artemis",
    category: "Agent platform",
    description: "Connect Kore.ai Artemis applications and monitor agent executions and tool interactions.",
    icon: <Bot size={24} />,
    status: "Available",
    method: "REST API / Adapter",
    setup: [
      "Register the Kore.ai application as an AgentOps agent.",
      "Identify execution lifecycle and tool events in the application.",
      "Map the application events to the AgentOps telemetry contract.",
      "Send events through the AgentOps ingestion API.",
    ],
  },
  {
    id: "langgraph",
    name: "LangGraph",
    category: "Agent framework",
    description: "Capture graph execution, node transitions, tool calls and agent workflow failures.",
    icon: <Workflow size={24} />,
    status: "Available",
    method: "Framework adapter",
    setup: [
      "Register the LangGraph agent.",
      "Instrument graph execution and node lifecycle events.",
      "Capture tool and model operations.",
      "Forward normalized telemetry to AgentOps.",
    ],
  },
  {
    id: "azure-foundry",
    name: "Azure AI Foundry",
    category: "Cloud AI platform",
    description: "Integrate agents developed with Azure AI Foundry, including locally running agent code.",
    icon: <Cloud size={24} />,
    status: "Available",
    method: "REST API / Adapter",
    setup: [
      "Register the agent and its environment.",
      "Identify the available agent execution and tool-call events.",
      "Map supported events to the AgentOps telemetry schema.",
      "Send telemetry from the agent runtime to AgentOps.",
    ],
  },
  {
    id: "openai-api",
    name: "OpenAI-compatible API",
    category: "API integration",
    description: "Connect custom applications and agent runtimes through an OpenAI-compatible integration layer.",
    icon: <Plug size={24} />,
    status: "Planned",
    method: "REST API",
    setup: [
      "Register the application in AgentOps.",
      "Configure the telemetry ingestion endpoint.",
      "Map model and tool operations to AgentOps events.",
      "Send execution and telemetry records.",
    ],
  },
  {
    id: "opentelemetry",
    name: "OpenTelemetry",
    category: "Observability standard",
    description: "Support standardized distributed traces, spans and telemetry collection.",
    icon: <Activity size={24} />,
    status: "Planned",
    method: "OTLP Collector",
    setup: [
      "Configure an OpenTelemetry Collector.",
      "Define the AgentOps telemetry mapping.",
      "Configure trace and span correlation.",
      "Forward supported telemetry into AgentOps.",
    ],
  },
];

export default function IntegrationsPage() {
  const [selected, setSelected] = useState<Integration | null>(null);
  const [category, setCategory] = useState("All");

  const categories = ["All", "Python SDK", "Agent platform", "Agent framework", "Cloud AI platform", "API integration", "Observability standard"];

  const filtered = integrations.filter(
    (item) => category === "All" || item.category === category
  );

  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-white">Integrations</h1>
            <p className="mt-1 text-sm text-slate-400">
              Connect agent frameworks, runtimes and external observability systems.
            </p>
          </div>
          <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-300">
            Integration setup · Local MVP
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Metric label="Supported integration paths" value="4" icon={<CheckCircle2 size={18} />} />
          <Metric label="Planned integrations" value="2" icon={<Circle size={18} />} />
          <Metric label="Connected integrations" value="0" icon={<Plug size={18} />} />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-white">Integration catalog</h2>
            <p className="mt-1 text-xs text-slate-400">
              Select an integration to view its setup approach.
            </p>
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-300 outline-none"
          >
            {categories.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {filtered.map((integration) => (
            <div
              key={integration.id}
              className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 transition hover:border-slate-700"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-slate-700 bg-slate-800 text-blue-400">
                  {integration.icon}
                </div>
                <span className={`rounded-full px-2.5 py-1 text-xs ${
                  integration.status === "Available"
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "bg-slate-700/60 text-slate-400"
                }`}>
                  {integration.status}
                </span>
              </div>

              <div className="mt-4">
                <p className="text-xs text-blue-400">{integration.category}</p>
                <h3 className="mt-1 text-base font-semibold text-white">{integration.name}</h3>
                <p className="mt-2 min-h-12 text-sm leading-6 text-slate-400">
                  {integration.description}
                </p>
              </div>

              <div className="mt-4 flex items-center justify-between border-t border-slate-800 pt-4">
                <span className="text-xs text-slate-500">{integration.method}</span>
                <button
                  onClick={() => setSelected(integration)}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs font-medium text-slate-200 transition hover:bg-slate-800"
                >
                  View setup <ArrowUpRight size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>

        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="flex items-center gap-3">
            <ShieldCheck size={20} className="text-emerald-400" />
            <h2 className="font-semibold text-white">Integration architecture</h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            AgentOps uses a normalized telemetry contract so different frameworks
            can send events into the same ingestion pipeline. Each integration
            translates its runtime-specific events into the common AgentOps format.
          </p>
          <div className="mt-5 grid grid-cols-1 gap-2 text-center text-xs sm:grid-cols-3">
            <div className="rounded-lg border border-slate-700 bg-slate-950 p-4">
              <p className="font-medium text-white">Agent runtimes</p>
              <p className="mt-1 text-slate-500">Python · Kore.ai · LangGraph · Foundry</p>
            </div>
            <div className="flex items-center justify-center text-slate-500">
              <span className="hidden sm:block">→</span>
              <span className="sm:hidden">↓</span>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-950 p-4">
              <p className="font-medium text-white">AgentOps ingestion</p>
              <p className="mt-1 text-slate-500">Normalized telemetry events</p>
            </div>
          </div>
        </section>

        {selected && (
          <div
            className="fixed inset-0 z-50 flex justify-end bg-black/60"
            onClick={() => setSelected(null)}
          >
            <aside
              onClick={(e) => e.stopPropagation()}
              className="h-full w-full max-w-xl overflow-y-auto border-l border-slate-800 bg-slate-950 p-6 shadow-2xl"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Integration setup</p>
                  <h2 className="mt-1 text-xl font-semibold text-white">{selected.name}</h2>
                  <p className="mt-2 text-sm text-slate-400">{selected.method}</p>
                </div>
                <button
                  onClick={() => setSelected(null)}
                  className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="mt-6 rounded-lg border border-slate-800 bg-slate-900 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-400">Implementation status</span>
                  <span className={`text-xs ${selected.status === "Available" ? "text-emerald-400" : "text-slate-400"}`}>
                    {selected.status}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-300">{selected.description}</p>
              </div>

              <div className="mt-7">
                <h3 className="font-semibold text-white">Setup approach</h3>
                <div className="mt-4 space-y-4">
                  {selected.setup.map((step, index) => (
                    <div key={step} className="flex gap-3">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-800 text-xs text-blue-400">
                        {index + 1}
                      </span>
                      <p className="pt-1 text-sm leading-6 text-slate-400">{step}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-7 rounded-lg border border-slate-800 bg-slate-900 p-4">
                <div className="flex items-center gap-2">
                  <Terminal size={16} className="text-blue-400" />
                  <h3 className="text-sm font-medium text-slate-200">API endpoint</h3>
                </div>
                <code className="mt-3 block break-all rounded bg-slate-950 p-3 text-xs text-emerald-300">
                  POST /api/v1/telemetry/events
                </code>
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  This is the existing local telemetry ingestion route. Configure
                  the full API base URL and authentication when integration credentials are implemented.
                </p>
              </div>

              <p className="mt-6 text-xs leading-5 text-slate-500">
                Opening this setup panel does not establish a connection. Integration
                registration, credentials and connectivity checks will be implemented
                in a later phase.
              </p>
            </aside>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function Metric({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex items-center justify-between text-slate-400">
        <span className="text-sm">{label}</span>
        {icon}
      </div>
      <div className="mt-3 text-3xl font-semibold tabular-nums text-white">{value}</div>
    </div>
  );
}
