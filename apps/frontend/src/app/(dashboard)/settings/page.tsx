import { requireUserOrRedirect } from "@/lib/server/session";
import { BACKEND_API_URL } from "@/lib/server/env";
import { formatDateTime } from "@/lib/format";
import ApiKeysSection from "@/components/settings/api-keys-section";

export default async function SettingsPage() {
  const user = await requireUserOrRedirect();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Settings</h1>
        <p className="text-sm text-slate-400">Your account and tenant scope.</p>
      </div>

      <div className="max-w-xl rounded-lg border border-slate-800 bg-slate-900/60 p-5">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Account</h2>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-500">Email</dt>
            <dd className="text-slate-200">{user.email}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Role</dt>
            <dd className="capitalize text-slate-200">{user.role}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Status</dt>
            <dd className="capitalize text-slate-200">{user.status}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Last login</dt>
            <dd className="text-slate-200">{formatDateTime(user.last_login_at)}</dd>
          </div>
        </dl>
      </div>

      <div className="max-w-xl rounded-lg border border-slate-800 bg-slate-900/60 p-5">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Tenant scope</h2>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-500">Organization</dt>
            <dd className="text-slate-200">{user.organization_name}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Project scope</dt>
            <dd className="text-slate-200">{user.project_name ?? "Entire organization"}</dd>
          </div>
        </dl>
        <p className="mt-3 text-xs text-slate-500">
          Every request this dashboard makes is authorized by your own session, scoped to this
          organization only - never by anything the browser itself supplies, and never visible to
          any other organization. See the trust boundary note in
          docs/architecture/m7-dashboard-and-auth.md.
        </p>
      </div>

      <div className="max-w-2xl rounded-lg border border-slate-800 bg-slate-900/60 p-5">
        <ApiKeysSection backendUrl={BACKEND_API_URL} />
      </div>
    </div>
  );
}
