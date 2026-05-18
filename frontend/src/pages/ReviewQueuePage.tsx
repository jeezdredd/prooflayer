import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { review } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";
import { Skeleton } from "../components/ui/Skeleton";
import { toast } from "../components/ui/Toast";

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
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["review-queue"] });
      setPendingId(null);
      toast.success(`Verdict overridden to ${vars.verdict}`);
    },
    onError: () => {
      setPendingId(null);
      toast.error("Override failed");
    },
  });

  if (!user?.is_staff) {
    return <div className="text-sm text-signal-blood font-mono">Staff access required.</div>;
  }

  return (
    <div>
      <div className="mb-6">
        <span className="label-mono">Service / 08</span>
        <h1 className="font-display text-4xl text-white mt-2">Review Queue</h1>
        <p className="text-sm text-ink-400 mt-2">
          Manually override verdicts for submissions flagged as <code className="text-ink-200">needs_review</code> or <code className="text-ink-200">inconclusive</code>.
        </p>
      </div>

      {isLoading && (
        <div className="space-y-3 animate-fade-in">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="case-card p-4 flex gap-4">
              <Skeleton className="w-24 h-24 rounded shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-3 w-1/4" />
                <Skeleton className="h-12 w-full mt-2" />
                <div className="flex gap-2">
                  <Skeleton className="h-7 w-20 rounded" />
                  <Skeleton className="h-7 w-20 rounded" />
                  <Skeleton className="h-7 w-20 rounded" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      {error && <div className="text-signal-blood text-sm font-mono">Failed to load queue.</div>}

      <div className="space-y-3">
        {(data || []).map((item) => {
          const reason = reasonById[item.id] || "";
          const isPending = pendingId === item.id && overrideMutation.isPending;
          return (
            <div key={item.id} className="case-card p-4 flex gap-4">
              <div className="w-24 h-24 bg-ink-900 border border-ink-800 overflow-hidden flex-shrink-0">
                {item.thumbnail_url ? (
                  <img src={item.thumbnail_url} alt="" className="w-full h-full object-cover" />
                ) : null}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <Link to={`/results/${item.id}`} className="font-mono text-sm text-ink-100 hover:text-iris truncate block transition">
                      {item.original_filename}
                    </Link>
                    <div className="font-mono text-[10px] text-ink-500 mt-0.5 ticker">
                      {item.submitter_email} · {new Date(item.created_at).toLocaleString()}
                      {item.override_count > 0 && (
                        <span className="ml-2 text-signal-amber">{item.override_count} prior override(s)</span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="badge border border-signal-violet/50 text-signal-violet bg-signal-violet/10">
                      {item.final_verdict}
                    </span>
                    {item.final_score !== null && (
                      <div className="font-mono text-[10px] text-ink-500 mt-1 tabular-nums">{Math.round(item.final_score * 100)}%</div>
                    )}
                  </div>
                </div>
                <textarea
                  className="w-full bg-ink-950/70 border border-ink-700 text-sm px-2 py-1 mb-2 font-mono text-ink-100 focus:outline-none focus:border-iris transition placeholder:text-ink-500"
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
                      className="font-mono text-[10px] uppercase tracking-[0.14em] px-3 py-1 border border-ink-700 text-ink-300 hover:border-iris hover:text-iris disabled:opacity-50 transition"
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
          <div className="text-center py-20 animate-fade-in">
            <div className="inline-flex items-center justify-center w-16 h-16 border border-sage-500/40 bg-sage-500/10 mb-3 text-3xl text-sage-300">
              ✓
            </div>
            <p className="font-mono text-sm text-ink-100">Queue empty</p>
            <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 mt-1">Nothing to review right now</p>
          </div>
        )}
      </div>
    </div>
  );
}
