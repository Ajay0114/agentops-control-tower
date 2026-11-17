
import type { ReactNode } from "react";
import AppSidebar from "./app-sidebar";
import AppHeader from "./app-header";

export default function AppShell({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <main className="app-shell">
      <AppSidebar />

      <section className="main-area">
        <AppHeader />

        {children}
      </section>
    </main>
  );
}
