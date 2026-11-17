
import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  Bot,
  CheckCircle2,
  ChevronDown,
  Clock3,
  MoreHorizontal,
  Plug,
  Zap,
} from "lucide-react";

import AppShell from "@/components/layout/app-shell";

const agents = [
  { name: "Customer Support Agent", type: "Custom Python", status: "Healthy", executions: 1248, success: "98.4%" },
  { name: "Knowledge Assistant", type: "LangGraph", status: "Healthy", executions: 856, success: "97.2%" },
  { name: "Home Delivery Agent", type: "Kore.ai Artemis", status: "Warning", executions: 432, success: "91.6%" },
  { name: "Document Processing Agent", type: "Azure AI Foundry", status: "Offline", executions: 218, success: "88.1%" },
];

const executions = [
  { id: "EX-8F21A9", agent: "Customer Support Agent", operation: "Customer query resolution", time: "Just now", duration: "2.4s", status: "Completed" },
  { id: "EX-8F21A8", agent: "Knowledge Assistant", operation: "Knowledge retrieval", time: "2 min ago", duration: "4.8s", status: "Completed" },
  { id: "EX-8F21A7", agent: "Home Delivery Agent", operation: "Order validation", time: "5 min ago", duration: "8.2s", status: "Failed" },
  { id: "EX-8F21A6", agent: "Customer Support Agent", operation: "Response generation", time: "8 min ago", duration: "1.9s", status: "Completed" },
  { id: "EX-8F21A5", agent: "Document Processing Agent", operation: "Document extraction", time: "12 min ago", duration: "6.1s", status: "Running" },
];

const activityBars = [
  34, 48, 42, 65, 52, 72, 59, 45, 76, 63, 84, 67,
  55, 73, 92, 68, 78, 59, 87, 72, 64, 82, 70, 96,
];

function Status({ value }: { value: string }) {
  const styles: Record<string, string> = {
    Completed: "status-success",
    Healthy: "status-success",
    Failed: "status-danger",
    Warning: "status-warning",
    Running: "status-info",
    Offline: "status-neutral",
  };

  return (
    <span className={`status ${styles[value] || "status-neutral"}`}>
      <span className="status-dot" />
      {value}
    </span>
  );
}

export default function Dashboard() {
  return (
    <AppShell>
      <div className="dashboard-content">
        <div className="page-heading">
          <div>
            <div className="eyebrow">PLATFORM OVERVIEW</div>
            <h1>Agent Operations</h1>
            <p>Monitor, analyze and manage your AI agent ecosystem.</p>
          </div>

          <div className="heading-actions">
            <button className="secondary-button">
              <Clock3 size={15} />
              Last 24 hours
              <ChevronDown size={14} />
            </button>
            <button className="primary-button">
              <Zap size={16} />
              Live monitoring
            </button>
          </div>
        </div>

        <div className="notice-banner">
          <div className="notice-icon"><Activity size={17} /></div>
          <div>
            <strong>Dashboard preview</strong>
            <span>
              Sample data is currently displayed. Connect your AgentOps APIs
              to view live agent activity.
            </span>
          </div>
          <span className="preview-tag">MOCK DATA</span>
        </div>

        <div className="section-heading">
          <div>
            <h2>Platform metrics</h2>
            <p>High-level view of your agent ecosystem</p>
          </div>
          <span className="updated-label">
            <span className="pulse-dot" />
            Updated just now
          </span>
        </div>

        <div className="metrics-grid">
          <Metric
            title="Registered agents"
            value="12"
            change="+2 this month"
            icon={<Bot size={19} />}
            trend="up"
          />
          <Metric
            title="Total executions"
            value="2,754"
            change="+18.6% vs previous"
            icon={<Activity size={19} />}
            trend="up"
          />
          <Metric
            title="Success rate"
            value="96.8%"
            change="+2.4% vs previous"
            icon={<CheckCircle2 size={19} />}
            trend="up"
          />
          <Metric
            title="Failed executions"
            value="89"
            change="-12.3% vs previous"
            icon={<AlertCircle size={19} />}
            trend="down"
          />
        </div>

        <div className="content-grid">
          <section className="panel activity-panel">
            <div className="panel-header">
              <div>
                <h2>Execution activity</h2>
                <p>Agent executions over the last 24 hours</p>
              </div>
              <button className="subtle-button">
                Hourly <ChevronDown size={14} />
              </button>
            </div>

            <div className="chart-summary">
              <div>
                <strong>2,754</strong>
                <span>Total executions</span>
              </div>
              <div className="chart-legend">
                <span className="legend-blue" /> Successful
                <span className="legend-red" /> Failed
              </div>
            </div>

            <div className="chart">
              <div className="chart-y-labels">
                <span>100</span><span>75</span><span>50</span>
                <span>25</span><span>0</span>
              </div>

              <div className="chart-plot">
                <div className="chart-grid-lines">
                  <i /><i /><i /><i /><i />
                </div>

                <div className="bars">
                  {activityBars.map((height, index) => (
                    <div className="bar-group" key={index}>
                      <div
                        className="bar-success"
                        style={{ height: `${height}%` }}
                      />
                      <div
                        className="bar-failed"
                        style={{ height: `${Math.max(4, height * 0.09)}%` }}
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="chart-x-labels">
              <span>00:00</span><span>04:00</span><span>08:00</span>
              <span>12:00</span><span>16:00</span><span>20:00</span>
              <span>Now</span>
            </div>
          </section>

          <section className="panel health-panel">
            <div className="panel-header">
              <div>
                <h2>Agent health</h2>
                <p>Current registered agent status</p>
              </div>
              <button className="icon-button">
                <MoreHorizontal size={19} />
              </button>
            </div>

            <div className="health-total">
              <strong>12</strong>
              <span>Registered agents</span>
            </div>

            <div className="health-bar">
              <span className="health-green" />
              <span className="health-yellow" />
              <span className="health-gray" />
            </div>

            <div className="health-legend">
              <div><span className="legend-green" /> Healthy <strong>9</strong></div>
              <div><span className="legend-yellow" /> Warning <strong>2</strong></div>
              <div><span className="legend-gray" /> Offline <strong>1</strong></div>
            </div>

            <div className="health-footer">
              <span>Availability across registered agents</span>
              <strong>75%</strong>
            </div>
          </section>
        </div>

        <section className="panel table-panel">
          <div className="panel-header table-heading">
            <div>
              <h2>Recent executions</h2>
              <p>Latest activity across your agent ecosystem</p>
            </div>
            <button className="secondary-button">
              View all executions <ArrowUpRight size={14} />
            </button>
          </div>

          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>EXECUTION ID</th>
                  <th>AGENT</th>
                  <th>OPERATION</th>
                  <th>STARTED</th>
                  <th>DURATION</th>
                  <th>STATUS</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {executions.map((execution) => (
                  <tr key={execution.id}>
                    <td><span className="execution-id">{execution.id}</span></td>
                    <td><strong className="agent-name-cell">{execution.agent}</strong></td>
                    <td>{execution.operation}</td>
                    <td>{execution.time}</td>
                    <td className="duration-cell">{execution.duration}</td>
                    <td><Status value={execution.status} /></td>
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
            <span>Showing 5 of 2,754 executions</span>
            <button>Explore executions <ArrowUpRight size={14} /></button>
          </div>
        </section>

        <div className="bottom-grid">
          <section className="panel agents-panel">
            <div className="panel-header">
              <div>
                <h2>Registered agents</h2>
                <p>Agent performance snapshot</p>
              </div>
              <button className="text-link">
                View all <ArrowUpRight size={14} />
              </button>
            </div>

            <div className="agent-list">
              {agents.map((agent) => (
                <div className="agent-row" key={agent.name}>
                  <div className="agent-symbol"><Bot size={19} /></div>
                  <div className="agent-details">
                    <strong>{agent.name}</strong>
                    <span>{agent.type}</span>
                  </div>
                  <div className="agent-performance">
                    <strong>{agent.success}</strong>
                    <span>{agent.executions.toLocaleString()} runs</span>
                  </div>
                  <Status value={agent.status} />
                </div>
              ))}
            </div>
          </section>

          <section className="panel activity-feed">
            <div className="panel-header">
              <div>
                <h2>Recent platform activity</h2>
                <p>Latest events and alerts</p>
              </div>
              <button className="icon-button">
                <MoreHorizontal size={19} />
              </button>
            </div>

            <div className="feed-list">
              <FeedItem
                icon={<CheckCircle2 size={16} />}
                color="green"
                title="Execution completed"
                detail="Customer Support Agent"
                time="Just now"
              />
              <FeedItem
                icon={<AlertCircle size={16} />}
                color="red"
                title="Execution failed"
                detail="Home Delivery Agent"
                time="5 min ago"
              />
              <FeedItem
                icon={<Bot size={16} />}
                color="blue"
                title="Agent registered"
                detail="Knowledge Assistant v1.2"
                time="1 hour ago"
              />
              <FeedItem
                icon={<Plug size={16} />}
                color="purple"
                title="Integration connected"
                detail="Local Python environment"
                time="3 hours ago"
              />
            </div>
          </section>
        </div>

        <footer className="footer">
          <span>AgentOps Control Tower <span className="footer-separator">·</span> Local development</span>
          <span>Platform preview <span className="footer-separator">·</span> v0.1.0</span>
        </footer>
      </div>
    </AppShell>
  );
}

function Metric({
  title,
  value,
  change,
  icon,
  trend,
}: {
  title: string;
  value: string;
  change: string;
  icon: React.ReactNode;
  trend: "up" | "down";
}) {
  return (
    <section className="metric-card">
      <div className="metric-top">
        <span>{title}</span>
        <div className="metric-icon">{icon}</div>
      </div>
      <div className="metric-value">{value}</div>
      <div className={`metric-change ${trend === "up" ? "trend-up" : "trend-down"}`}>
        {trend === "up" ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
        {change}
      </div>
    </section>
  );
}

function FeedItem({
  icon,
  color,
  title,
  detail,
  time,
}: {
  icon: React.ReactNode;
  color: string;
  title: string;
  detail: string;
  time: string;
}) {  
  return (
    <div className="feed-item">
      <div className={`feed-icon feed-${color}`}>{icon}</div>
      <div className="feed-details">
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
      <time>{time}</time>
    </div>
  );
}
