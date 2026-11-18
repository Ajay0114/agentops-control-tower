const STATUS_STYLES: Record<string, string> = {
  completed: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  succeeded: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  active: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  registered: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  running: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  started: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  queued: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  failed: "bg-red-500/10 text-red-400 border-red-500/20",
  error: "bg-red-500/10 text-red-400 border-red-500/20",
  cancelled: "bg-slate-500/10 text-slate-400 border-slate-500/20",
  inactive: "bg-slate-500/10 text-slate-400 border-slate-500/20",
  archived: "bg-slate-500/10 text-slate-400 border-slate-500/20",
};

const DEFAULT_STYLE = "bg-slate-500/10 text-slate-400 border-slate-500/20";

export default function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status.toLowerCase()] ?? DEFAULT_STYLE;

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${style}`}
    >
      {status}
    </span>
  );
}
