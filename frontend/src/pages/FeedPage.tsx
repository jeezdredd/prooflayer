import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Link } from "react-router-dom";
import { Globe, User, Calendar } from "lucide-react";
import { feed } from "../api/endpoints";
import type { PublicSubmission } from "../types";
import { Skeleton } from "../components/ui/Skeleton";

function VerdictBadge({ verdict, score }: { verdict: string; score: number | null }) {
  const isAI = verdict === "ai_generated";
  const isReal = verdict === "authentic";
  const color = isAI
    ? "text-signal-blood border-signal-blood/40 bg-signal-blood/5"
    : isReal
    ? "text-signal-sage border-signal-sage/40 bg-signal-sage/5"
    : "text-signal-amber border-signal-amber/40 bg-signal-amber/5";
  const label = isAI ? "AI" : isReal ? "Real" : verdict?.replace("_", " ") || "Unknown";

  return (
    <span className={`font-mono text-[9px] uppercase tracking-[0.14em] border px-2 py-0.5 rounded-full ${color}`}>
      {label}
      {score !== null && ` ${Math.round(score * 100)}%`}
    </span>
  );
}

function FeedCard({ item }: { item: PublicSubmission }) {
  const mimePrefix = item.mime_type?.split("/")[0];
  const isImage = mimePrefix === "image";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="case-card overflow-hidden group hover:border-iris/30 transition-colors"
    >
      <Link to={`/feed/${item.id}`} className="block">
        <div className="aspect-video bg-ink-900 relative overflow-hidden">
          {isImage && item.thumbnail_url ? (
            <img
              src={item.thumbnail_url}
              alt={item.original_filename}
              className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-500"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-600">
                {item.mime_type || "Unknown"}
              </span>
            </div>
          )}
          <div className="absolute top-2 right-2">
            <VerdictBadge verdict={item.final_verdict} score={item.final_score} />
          </div>
        </div>
        <div className="p-4">
          <div className="font-mono text-xs text-ink-200 truncate mb-3" title={item.original_filename}>
            {item.original_filename}
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-ink-500">
              <User size={11} strokeWidth={1.5} />
              <span className="font-mono text-[10px]">{item.uploader.username}</span>
            </div>
            <div className="flex items-center gap-1.5 text-ink-600">
              <Calendar size={11} strokeWidth={1.5} />
              <span className="font-mono text-[10px]">
                {new Date(item.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

function FeedCardSkeleton() {
  return (
    <div className="case-card overflow-hidden">
      <Skeleton className="aspect-video w-full" />
      <div className="p-4 space-y-3">
        <Skeleton className="h-3 w-3/4" />
        <div className="flex justify-between">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
    </div>
  );
}

export default function FeedPage() {
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["feed", page],
    queryFn: () => feed.list({ page: String(page) }).then((r) => r.data),
  });

  return (
    <div>
      <div className="mb-10">
        <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-600 mb-3">
          Community / Public Feed
        </div>
        <div className="flex items-center gap-3 mb-2">
          <Globe size={20} strokeWidth={1.5} className="text-iris" />
          <h1 className="font-display text-3xl text-ink-50">Public Submissions</h1>
        </div>
        <p className="text-ink-400 text-sm max-w-xl">
          Verified content shared by the ProofLayer community. Toggle &quot;Public&quot; on your results page to appear here.
        </p>
      </div>

      {isError && (
        <div className="text-center py-20">
          <p className="text-ink-400 font-mono text-sm">Failed to load feed.</p>
        </div>
      )}

      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <FeedCardSkeleton key={i} />
          ))}
        </div>
      )}

      {data && data.results.length === 0 && (
        <div className="text-center py-20">
          <Globe size={40} strokeWidth={1} className="text-ink-700 mx-auto mb-4" />
          <p className="text-ink-400 font-mono text-sm mb-2">No public submissions yet.</p>
          <p className="text-ink-600 font-mono text-[11px]">
            Be the first - toggle &quot;Public&quot; on any completed result.
          </p>
        </div>
      )}

      {data && data.results.length > 0 && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {data.results.map((item) => (
              <FeedCard key={item.id} item={item} />
            ))}
          </div>

          <div className="flex items-center justify-between mt-8 font-mono text-[11px] uppercase tracking-[0.14em]">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={!data.previous}
              className="px-4 py-2 border border-ink-700 text-ink-400 hover:text-ink-200 hover:border-ink-500 transition disabled:opacity-30 disabled:cursor-not-allowed"
            >
              &larr; Prev
            </button>
            <span className="text-ink-600">
              {data.count} submission{data.count !== 1 ? "s" : ""}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={!data.next}
              className="px-4 py-2 border border-ink-700 text-ink-400 hover:text-ink-200 hover:border-ink-500 transition disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Next &rarr;
            </button>
          </div>
        </>
      )}
    </div>
  );
}
