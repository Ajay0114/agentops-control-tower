import type { ReactNode } from "react";

import AppShell from "@/components/layout/app-shell";
import { requireUserOrRedirect } from "@/lib/server/session";

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  // The authoritative session check for every protected page: re-validates
  // the session cookie against the backend on every navigation into this
  // route group (proxy.ts's own check is only a fast, optimistic redirect
  // for requests with no cookie at all - see its module comment).
  const user = await requireUserOrRedirect();

  return <AppShell user={user}>{children}</AppShell>;
}
