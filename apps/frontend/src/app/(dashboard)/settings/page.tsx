import { requireUserOrRedirect } from "@/lib/server/session";
import { formatDateTime } from "@/lib/format";

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
            <dt className="text-slate-500">Organization ID</dt>
            <dd className="font-mono text-xs text-slate-200">{user.organization_id}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Project scope</dt>
            <dd className="font-mono text-xs text-slate-200">
              {user.project_id ?? "Entire organization"}
            </dd>
          </div>
        </dl>
        <p className="mt-3 text-xs text-slate-500">
          This is informational only. Every request to the AgentOps API is authorized by this
          deployment&apos;s own server-side API key, never by this account&apos;s stated scope -
          see the trust boundary note in docs/architecture/m7-dashboard-and-auth.md.
        </p>
      </div>
    </div>
  );
}
