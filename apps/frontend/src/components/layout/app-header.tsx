
"use client";

import { usePathname } from "next/navigation";
import { Search, Settings } from "lucide-react";

const pageNames: Record<string, string> = {
  "/": "Overview",
  "/agents": "Agents",
  "/executions": "Executions",
  "/traces": "Traces",
  "/telemetry": "Telemetry",
  "/integrations": "Integrations",
  "/policies": "Policies",
  "/settings": "Settings",
};

export default function AppHeader() {
  const pathname = usePathname();
  const pageName = pageNames[pathname] ?? "Platform";

  return (
    <header className="topbar">
      <div className="breadcrumb">
        Platform <span>/</span> <strong>{pageName}</strong>
      </div>

      <div className="topbar-actions">
        <div className="environment-pill">
          <span />
          DEVELOPMENT
        </div>

        <button className="icon-button" aria-label="Search">
          <Search size={18} />
        </button>

        <button className="icon-button" aria-label="Settings">
          <Settings size={18} />
        </button>

        <div className="topbar-divider" />

        <div className="user-avatar top-avatar">AK</div>
      </div>
    </header>
  );
}
