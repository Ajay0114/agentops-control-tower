
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bot,
  Command,
  FolderTree,
  GitBranch,
  LayoutDashboard,
  Settings,
  Users,
} from "lucide-react";

import type { CurrentUser } from "@/lib/types";

const navigation = [
  { label: "Overview", href: "/", icon: LayoutDashboard },
  { label: "Agents", href: "/agents", icon: Bot },
  { label: "Executions", href: "/executions", icon: Activity },
  { label: "Sessions", href: "/sessions", icon: Users },
  { label: "Traces", href: "/traces", icon: GitBranch },
  { label: "Environments", href: "/environments", icon: FolderTree },
  { label: "Settings", href: "/settings", icon: Settings },
];

export default function AppSidebar({ user }: { user: CurrentUser }) {
  const pathname = usePathname();

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
        <div className="workspace-avatar">{user.email.slice(0, 1).toUpperCase()}</div>
        <div className="workspace-info">
          <strong>Local organization</strong>
          <span>{user.project_id ? "Scoped to one project" : "Organization-wide access"}</span>
        </div>
      </div>

      <div className="nav-label">PLATFORM</div>
      <nav className="navigation">
        {navigation.map((item) => {
          const Icon = item.icon;
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item ${active ? "nav-active" : ""}`}
            >
              <Icon size={18} strokeWidth={1.8} />
              <span>{item.label}</span>
            </Link>
          );
        })}
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
          <div className="user-avatar">{user.email.slice(0, 2).toUpperCase()}</div>
          <div className="user-info">
            <strong>{user.email}</strong>
            <span className="capitalize">{user.role}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
