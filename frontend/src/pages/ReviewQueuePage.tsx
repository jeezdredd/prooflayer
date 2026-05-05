import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { review } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";

const VERDICT_OPTIONS = ["authentic", "suspicious", "likely_fake", "fake", "inconclusive"] as const;

type QueueItem = {
  id: string;
  original_filename: string;
  thumbnail_url: string | null;
  final_verdict: string;
  final_score: number | null;
  submitter_email: string;
  override_count: number;
  created_at: string;
};

export default function ReviewQueuePage() {
  const { user } = useAuthStore();
  const qc = useQueryClient();
  const [reasonById, setReasonById] = useState<Record<string, string>>({});
  const [pendingId, setPendingId] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["review-queue"],
    queryFn: async () => {
      const res = await review.queue();
      return res.data.results as QueueItem[];
    },
    enabled: !!user?.is_staff,
  });

  const overrideMutation = useMutation({
    mutationFn: ({ id, verdict, reason }: { id: string; verdict: string; reason: string }) =>
      review.override(id, { verdict, reason }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["review-queue"] });
      setPendingId(null);
    },
  });

  if (!user?.is_staff) {
    return <div className="text-sm text-red-600">Staff access required.</div>;
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Review Queue</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manually override verdicts for submissions flagged as <code>needs_review</code> or <code>inconclusive</code>.
        </p>
      </div>

      {isLoading && <div className="text-gray-500 text-sm">Loading…</div>}
      {error && <div className="text-red-600 text-sm">Failed to load queue.</div>}

      <div className="space-y-3">
        {(data || []).map((item) => {
          const reason = reasonById[item.id] || "";
          const isPending = pendingId === item.id && overrideMutation.isPending;
          return (
            <div key={item.id} className="bg-white border border-gray-200 rounded-lg p-4 flex gap-4">
              <div className="w-24 h-24 bg-gray-100 rounded overflow-hidden flex-shrink-0">
                {item.thumbnail_url ? (
                  <img src={item.thumbnail_url} alt="" className="w-full h-full object-cover" />
                ) : null}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <Link to={`/results/${item.id}`} className="font-medium text-gray-900 hover:underline truncate block">
                      {item.original_filename}
                    </Link>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {item.submitter_email} · {new Date(item.created_at).toLocaleString()}
                      {item.override_count > 0 && (
                        <span className="ml-2 text-amber-600">{item.override_count} prior override(s)</span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xs uppercase tracking-wide text-purple-700 bg-purple-100 px-2 py-0.5 rounded">
                      {item.final_verdict}
                    </span>
                    {item.final_score !== null && (
                      <div className="text-xs text-gray-500 mt-1">{Math.round(item.final_score * 100)}%</div>
                    )}
                  </div>
                </div>
                <textarea
                  className="w-full border border-gray-300 rounded text-sm px-2 py-1 mb-2"
                  placeholder="Reason for override (optional)"
                  rows={2}
                  value={reason}
                  onChange={(e) => setReasonById((prev) => ({ ...prev, [item.id]: e.target.value }))}
                />
                <div className="flex gap-2 flex-wrap">
                  {VERDICT_OPTIONS.map((v) => (
                    <button
                      key={v}
                      onClick={() => {
                        setPendingId(item.id);
                        overrideMutation.mutate({ id: item.id, verdict: v, reason });
                      }}
                      disabled={isPending}
                      className="px-3 py-1 text-xs rounded border border-gray-300 hover:bg-gray-100 disabled:opacity-50"
                    >
                      {v.replace("_", " ")}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
        {data && data.length === 0 && !isLoading && (
          <div className="text-gray-500 text-sm">Queue empty. Nothing to review.</div>
        )}
      </div>
    </div>
  );
}
