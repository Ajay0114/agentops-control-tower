
"use client";

import { useRouter, usePathname } from "next/navigation";
import { useState } from "react";
import { LogOut, ChevronDown } from "lucide-react";

import { logout } from "@/lib/api/client";
import type { CurrentUser } from "@/lib/types";

const pageNames: Record<string, string> = {
  "/": "Overview",
  "/agents": "Agents",
  "/executions": "Executions",
  "/sessions": "Sessions",
  "/traces": "Traces",
  "/environments": "Environments",
  "/settings": "Settings",
};

function pageNameFor(pathname: string): string {
  if (pageNames[pathname]) return pageNames[pathname];

  const topSegment = "/" + pathname.split("/")[1];
  return pageNames[topSegment] ?? "Platform";
}

export default function AppHeader({ user }: { user: CurrentUser }) {
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  const pageName = pageNameFor(pathname);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      router.push("/login");
      router.refresh();
    }
  }

  return (
    <header className="topbar">
      <div className="breadcrumb">
        Platform <span>/</span> <strong>{pageName}</strong>
      </div>

      <div className="topbar-actions">
        <div className="relative">
          <button
            className="icon-button flex items-center gap-2 px-2"
            onClick={() => setMenuOpen((open) => !open)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <div className="user-avatar top-avatar">{user.email.slice(0, 2).toUpperCase()}</div>
            <ChevronDown size={14} />
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-full z-10 mt-2 w-56 rounded-md border border-slate-700 bg-slate-900 p-2 shadow-lg"
            >
              <div className="px-2 py-1.5 text-sm text-slate-300">{user.email}</div>
              <div className="px-2 pb-1.5 text-xs capitalize text-slate-500">{user.role}</div>
              <hr className="my-1 border-slate-800" />
              <button
                role="menuitem"
                disabled={loggingOut}
                onClick={handleLogout}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
              >
                <LogOut size={14} />
                {loggingOut ? "Signing out…" : "Sign out"}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
