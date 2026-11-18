import type { ReactNode } from "react";
import { AlertTriangle, Inbox } from "lucide-react";

export function LoadingSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading" className="space-y-2">
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="h-10 w-full animate-pulse rounded-md bg-slate-800/60"
        />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  icon,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-slate-700 py-16 text-center">
      {icon ?? <Inbox size={28} className="text-slate-500" />}
      <p className="font-medium text-slate-200">{title}</p>
      {description && <p className="max-w-sm text-sm text-slate-400">{description}</p>}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-red-500/20 bg-red-500/5 py-16 text-center">
      <AlertTriangle size={28} className="text-red-400" />
      <p className="font-medium text-red-300">Something went wrong</p>
      <p className="max-w-sm text-sm text-slate-400">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-1 rounded-md border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function UnavailableMetric() {
  return <span className="text-slate-500" title="No data reported yet">—</span>;
}
