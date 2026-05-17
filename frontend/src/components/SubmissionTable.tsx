import clsx from "clsx";
import { useNavigate } from "react-router-dom";
import type { PaginatedResponse, SubmissionListItem } from "../types";
import { Skeleton } from "./ui/Skeleton";

interface SubmissionTableProps {
  data: PaginatedResponse<SubmissionListItem> | undefined;
  isLoading: boolean;
  page: number;
  onPageChange: (page: number) => void;
}

const VERDICT_TONE: Record<string, { color: string; label: string }> = {
  authentic: { color: "text-signal-sage", label: "Authentic" },
  suspicious: { color: "text-signal-amber", label: "Suspicious" },
  likely_fake: { color: "text-signal-blood", label: "Likely Fake" },
  fake: { color: "text-signal-blood", label: "Fake" },
  needs_review: { color: "text-signal-violet", label: "Needs Review" },
  inconclusive: { color: "text-ink-300", label: "Inconclusive" },
};

const STATUS_TONE: Record<string, string> = {
  completed: "text-signal-sage",
  processing: "text-signal-amber",
  pending: "text-signal-amber",
  failed: "text-signal-blood",
};

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}K`;
  return `${(bytes / 1024 / 1024).toFixed(1)}M`;
}

export default function SubmissionTable({ data, isLoading, page, onPageChange }: SubmissionTableProps) {
  const navigate = useNavigate();
  const pageSize = 20;
  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  if (isLoading) {
    return (
      <div className="case-card crop-marks animate-fade-in">
        <div className="px-4 py-3 border-b border-ink-700">
          <Skeleton className="h-3 w-32" />
        </div>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="border-b border-ink-800 last:border-0 px-4 py-3 flex items-center gap-4">
            <Skeleton className="w-12 h-12" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-2/5" />
              <Skeleton className="h-2 w-1/4" />
            </div>
            <Skeleton className="h-3 w-12" />
            <Skeleton className="h-5 w-20" />
          </div>
        ))}
      </div>
    );
  }

  if (!data || data.results.length === 0) {
    return (
      <div className="case-card crop-marks py-20 text-center animate-fade-in">
        <div className="font-display text-5xl text-ink-300 mb-2">∅</div>
        <p className="label-mono text-ink-200">Registry empty</p>
        <p className="font-mono text-[11px] text-ink-500 mt-2">
          Submit a file to seed the dossier.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="case-card crop-marks">
        {/* Header row */}
        <div className="grid grid-cols-[40px_1fr_120px_80px_80px_120px] gap-4 px-4 py-3 border-b border-ink-700 font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500">
          <span>#</span>
          <span>File · Hash</span>
          <span>Date</span>
          <span>Size</span>
          <span className="text-right">Score</span>
          <span className="text-right">Verdict</span>
        </div>

        {data.results.map((sub, idx) => {
          const tone = VERDICT_TONE[sub.final_verdict] || VERDICT_TONE.inconclusive;
          const statusColor = STATUS_TONE[sub.status] || "text-ink-400";
          const isComplete = sub.status === "completed";
          return (
            <div
              key={sub.id}
              onClick={() => navigate(`/results/${sub.id}`)}
              className="grid grid-cols-[40px_1fr_120px_80px_80px_120px] gap-4 px-4 py-3 border-b border-ink-800 last:border-0 cursor-pointer hover:bg-ink-850 transition-colors group items-center"
            >
              <span className="font-mono text-[10px] text-ink-500 ticker">
                {String((page - 1) * pageSize + idx + 1).padStart(3, "0")}
              </span>
              <div className="flex items-center gap-3 min-w-0">
                {sub.thumbnail_url ? (
                  <img
                    src={sub.thumbnail_url}
                    alt=""
                    className="w-10 h-10 object-cover border border-ink-700 grayscale group-hover:grayscale-0 transition-all"
                  />
                ) : (
                  <div className="w-10 h-10 border border-ink-700 bg-ink-900 flex items-center justify-center font-mono text-[9px] text-ink-500">
                    {sub.mime_type?.split("/")[1]?.slice(0, 4).toUpperCase() || "FILE"}
                  </div>
                )}
                <div className="min-w-0">
                  <div className="font-mono text-xs text-ink-100 truncate group-hover:text-signal-amber transition-colors">
                    {sub.original_filename}
                  </div>
                  <div className="font-mono text-[9px] text-ink-500 mt-0.5 ticker">
                    {sub.id.slice(0, 8).toUpperCase()}
                  </div>
                </div>
              </div>
              <span className="font-mono text-[10px] text-ink-400 ticker">
                {new Date(sub.created_at).toISOString().slice(0, 10)}
              </span>
              <span className="font-mono text-[10px] text-ink-400 ticker">
                {formatSize(sub.file_size)}
              </span>
              <span
                className={clsx(
                  "font-mono text-xs text-right ticker",
                  isComplete ? tone.color : statusColor,
                )}
              >
                {isComplete && sub.final_score !== null
                  ? `${Math.round(sub.final_score * 100)}%`
                  : "-"}
              </span>
              <span className="text-right">
                <span
                  className={clsx(
                    "badge",
                    isComplete ? tone.color : statusColor,
                    "border-current",
                  )}
                >
                  {isComplete ? tone.label : sub.status}
                </span>
              </span>
            </div>
          );
        })}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 font-mono text-[10px] uppercase tracking-[0.14em]">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page === 1}
            className="text-ink-400 hover:text-ink-100 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            ← Prev
          </button>
          <span className="text-ink-500 ticker">
            Page {String(page).padStart(2, "0")} / {String(totalPages).padStart(2, "0")} · {data.count} total
          </span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page === totalPages}
            className="text-ink-400 hover:text-ink-100 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
