
import type { ReactNode } from "react";
import AppSidebar from "./app-sidebar";
import AppHeader from "./app-header";
import type { CurrentUser } from "@/lib/types";

export default function AppShell({
  children,
  user,
}: {
  children: ReactNode;
  user: CurrentUser;
}) {
  return (
    <main className="app-shell">
      <AppSidebar user={user} />

      <section className="main-area">
        <AppHeader user={user} />

        {children}
      </section>
    </main>
  );
}
