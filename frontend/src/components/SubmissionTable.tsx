import clsx from "clsx";
import { useNavigate } from "react-router-dom";
import type { PaginatedResponse, SubmissionListItem } from "../types";

interface SubmissionTableProps {
  data: PaginatedResponse<SubmissionListItem> | undefined;
  isLoading: boolean;
  page: number;
  onPageChange: (page: number) => void;
}

const VERDICT_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  authentic: { bg: "bg-green-100", text: "text-green-800", label: "Authentic" },
  suspicious: { bg: "bg-yellow-100", text: "text-yellow-800", label: "Suspicious" },
  likely_fake: { bg: "bg-orange-100", text: "text-orange-800", label: "Likely Fake" },
  fake: { bg: "bg-red-100", text: "text-red-800", label: "Fake" },
  needs_review: { bg: "bg-purple-100", text: "text-purple-800", label: "Needs Review" },
  inconclusive: { bg: "bg-gray-100", text: "text-gray-800", label: "Inconclusive" },
};

export default function SubmissionTable({ data, isLoading, page, onPageChange }: SubmissionTableProps) {
  const navigate = useNavigate();
  const pageSize = 20;
  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!data || data.results.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400 text-sm">
        No submissions found.
      </div>
    );
  }

  return (
    <div>
      <div className="space-y-2">
        {data.results.map((sub) => {
          const verdict = VERDICT_STYLES[sub.final_verdict] || VERDICT_STYLES.inconclusive;
          return (
            <div
              key={sub.id}
              onClick={() => navigate(`/results/${sub.id}`)}
              className="flex items-center gap-4 p-4 bg-white rounded-xl border border-gray-200 cursor-pointer hover:border-gray-300 transition-colors"
            >
              {sub.thumbnail_url ? (
                <img
                  src={sub.thumbnail_url}
                  alt={sub.original_filename}
                  className="w-12 h-12 object-cover rounded-lg flex-shrink-0"
                />
              ) : (
                <div className="w-12 h-12 bg-gray-100 rounded-lg flex-shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{sub.original_filename}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {new Date(sub.created_at).toLocaleDateString()} &middot; {(sub.file_size / 1024).toFixed(0)} KB
                </p>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                {sub.final_score !== null && (
                  <span className="text-sm font-semibold text-gray-700">
                    {(sub.final_score * 100).toFixed(0)}%
                  </span>
                )}
                <span className={clsx("text-xs px-2 py-1 rounded-full font-medium", verdict.bg, verdict.text)}>
                  {sub.status === "completed" ? verdict.label : sub.status}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page === 1}
            className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-40"
          >
            &larr; Previous
          </button>
          <span className="text-sm text-gray-400">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page === totalPages}
            className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-40"
          >
            Next &rarr;
          </button>
        </div>
      )}
    </div>
  );
}
