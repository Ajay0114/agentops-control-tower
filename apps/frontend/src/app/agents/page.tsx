
import {
  Bot,
  Plus,
  Search,
  Filter,
  MoreHorizontal,
  Activity,
  Clock3,
  CheckCircle2,
  AlertCircle,
  ArrowUpRight,
} from "lucide-react";

import AppShell from "@/components/layout/app-shell";

const agents = [
  {
    name: "Customer Support Agent",
    description: "Handles customer queries and support workflows",
    framework: "Custom Python",
    environment: "Development",
    version: "v1.0.0",
    status: "Healthy",
    executions: "1,248",
    success: "98.4%",
    lastActive: "Just now",
  },
  {
    name: "Knowledge Assistant",
    description: "Retrieves and processes enterprise knowledge",
    framework: "LangGraph",
    environment: "Development",
    version: "v1.2.0",
    status: "Healthy",
    executions: "856",
    success: "97.2%",
    lastActive: "2 min ago",
  },
  {
    name: "Home Delivery Agent",
    description: "Processes home delivery product requests",
    framework: "Kore.ai Artemis",
    environment: "Development",
    version: "v1.0.0",
    status: "Warning",
    executions: "432",
    success: "91.6%",
    lastActive: "5 min ago",
  },
  {
    name: "Document Processing Agent",
    description: "Extracts and processes document information",
    framework: "Azure AI Foundry",
    environment: "Local",
    version: "v1.0.0",
    status: "Offline",
    executions: "218",
    success: "88.1%",
    lastActive: "2 hours ago",
  },
];

function Status({ value }: { value: string }) {
  const styles: Record<string, string> = {
    Healthy: "status-success",
    Warning: "status-warning",
    Offline: "status-neutral",
  };

  return (
    <span className={`status ${styles[value] || "status-neutral"}`}>
      <span className="status-dot" />
      {value}
    </span>
  );
}

export default function AgentsPage() {
  return (
    <AppShell>
      <div className="dashboard-content">
        <div className="page-heading">
          <div>
            <div className="eyebrow">AGENT MANAGEMENT</div>
            <h1>Agents Registry</h1>
            <p>Register, monitor and manage agents across your ecosystem.</p>
          </div>

          <button className="primary-button">
            <Plus size={16} />
            Register agent
          </button>
        </div>

        <div className="metrics-grid">
          <Metric title="Total agents" value="12" icon={<Bot size={18} />} />
          <Metric title="Healthy" value="9" icon={<CheckCircle2 size={18} />} />
          <Metric title="Warning" value="2" icon={<AlertCircle size={18} />} />
          <Metric title="Offline" value="1" icon={<Activity size={18} />} />
        </div>

        <section className="panel table-panel">
          <div className="panel-header table-heading">
            <div>
              <h2>Registered agents</h2>
              <p>All agents registered in your organization</p>
            </div>
            <button className="secondary-button">
              <Filter size={14} /> Filters
            </button>
          </div>

          <div className="agent-toolbar">
            <div className="agent-search">
              <Search size={16} />
              <input placeholder="Search agents..." />
            </div>

            <span className="agent-result-count">
              Showing {agents.length} agents
            </span>
          </div>

          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>AGENT</th>
                  <th>FRAMEWORK</th>
                  <th>ENVIRONMENT</th>
                  <th>VERSION</th>
                  <th>EXECUTIONS</th>
                  <th>SUCCESS RATE</th>
                  <th>STATUS</th>
                  <th>LAST ACTIVE</th>
                  <th />
                </tr>
              </thead>

              <tbody>
                {agents.map((agent) => (
                  <tr key={agent.name}>
                    <td>
                      <div className="agent-table-name">
                        <div className="agent-symbol">
                          <Bot size={18} />
                        </div>
                        <div>
                          <strong>{agent.name}</strong>
                          <span>{agent.description}</span>
                        </div>
                      </div>
                    </td>
                    <td>{agent.framework}</td>
                    <td>{agent.environment}</td>
                    <td>{agent.version}</td>
                    <td>{agent.executions}</td>
                    <td className="agent-success-rate">{agent.success}</td>
                    <td><Status value={agent.status} /></td>
                    <td>{agent.lastActive}</td>
                    <td>
                      <button className="row-action">
                        <MoreHorizontal size={18} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="table-footer">
            <span>Sample agent registry data</span>
            <button>
              View agent details <ArrowUpRight size={14} />
            </button>
          </div>
        </section>

        <section className="panel registry-info">
          <div className="registry-info-icon">
            <Clock3 size={19} />
          </div>
          <div>
            <h2>Agent registration and discovery</h2>
            <p>
              Agents will be registered through the AgentOps API or discovered
              through supported runtime integrations. Local agent discovery
              will be added in the integration phase.
            </p>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function Metric({
  title,
  value,
  icon,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <section className="metric-card">
      <div className="metric-top">
        <span>{title}</span>
        <div className="metric-icon">{icon}</div>
      </div>
      <div className="metric-value">{value}</div>
    </section>
  );
}
