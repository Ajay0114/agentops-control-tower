
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bot,
  Command,
  Database,
  GitBranch,
  LayoutDashboard,
  Plug,
  Settings,
  ShieldCheck,
} from "lucide-react";

const platformNavigation = [
  { label: "Overview", href: "/", icon: LayoutDashboard },
  { label: "Agents", href: "/agents", icon: Bot },
  { label: "Executions", href: "/executions", icon: Activity },
  { label: "Traces", href: "/traces", icon: GitBranch },
  { label: "Telemetry", href: "/telemetry", icon: Database },
  { label: "Integrations", href: "/integrations", icon: Plug },
];

const governanceNavigation = [
  { label: "Policies", href: "/policies", icon: ShieldCheck },
  { label: "Settings", href: "/settings", icon: Settings },
];

export default function AppSidebar() {
  const pathname = usePathname();

  const renderNavigation = (
    items: typeof platformNavigation,
  ) =>
    items.map((item) => {
      const Icon = item.icon;
      const active =
        item.href === "/"
          ? pathname === "/"
          : pathname.startsWith(item.href);

      return (
        <Link
          key={item.href}
          href={item.href}
          className={`nav-item ${active ? "nav-active" : ""}`}
        >
          <Icon size={18} strokeWidth={1.8} />
          <span>{item.label}</span>
          {item.href === "/agents" && (
            <span className="nav-count">12</span>
          )}
        </Link>
      );
    });

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon">
          <Command size={21} />
        </div>
        <div>
          <div className="brand-name">AgentOps</div>
          <div className="brand-caption">CONTROL TOWER</div>
        </div>
      </div>

      <div className="workspace">
        <div className="workspace-avatar">A</div>
        <div className="workspace-info">
          <strong>AgentOps Workspace</strong>
          <span>Local organization</span>
        </div>
      </div>

      <div className="nav-label">PLATFORM</div>
      <nav className="navigation">
        {renderNavigation(platformNavigation)}
      </nav>

      <div className="nav-label governance-label">GOVERNANCE</div>
      <nav className="navigation">
        {renderNavigation(governanceNavigation)}
      </nav>

      <div className="sidebar-bottom">
        <div className="connection-indicator">
          <span className="pulse-dot" />
          <div>
            <strong>Local environment</strong>
            <span>Platform connected</span>
          </div>
        </div>

        <div className="user-profile">
          <div className="user-avatar">AK</div>
          <div className="user-info">
            <strong>Administrator</strong>
            <span>Local account</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
