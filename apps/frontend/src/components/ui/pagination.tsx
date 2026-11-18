import { ChevronLeft, ChevronRight } from "lucide-react";

export default function Pagination({
  offset,
  limit,
  total,
  onPageChange,
}: {
  offset: number;
  limit: number;
  total: number | null;
  onPageChange: (newOffset: number) => void;
}) {
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = total !== null ? Math.max(1, Math.ceil(total / limit)) : null;
  const hasNext = total !== null ? offset + limit < total : true;
  const hasPrev = offset > 0;

  return (
    <div className="flex items-center justify-between border-t border-slate-800 pt-3 text-sm text-slate-400">
      <span>
        {total !== null
          ? `${total === 0 ? 0 : offset + 1}-${Math.min(offset + limit, total)} of ${total}`
          : `Page ${currentPage}`}
      </span>

      <div className="flex items-center gap-2">
        <button
          aria-label="Previous page"
          disabled={!hasPrev}
          onClick={() => onPageChange(Math.max(0, offset - limit))}
          className="flex items-center gap-1 rounded-md border border-slate-700 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-40 hover:not-disabled:bg-slate-800"
        >
          <ChevronLeft size={14} /> Prev
        </button>
        <span>
          {currentPage}
          {totalPages ? ` / ${totalPages}` : ""}
        </span>
        <button
          aria-label="Next page"
          disabled={!hasNext}
          onClick={() => onPageChange(offset + limit)}
          className="flex items-center gap-1 rounded-md border border-slate-700 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-40 hover:not-disabled:bg-slate-800"
        >
          Next <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
