import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Globe, User, Calendar, ArrowLeft } from "lucide-react";
import { feed } from "../api/endpoints";
import { Skeleton } from "../components/ui/Skeleton";

function VerdictBadge({ verdict, score }: { verdict: string; score: number | null }) {
  const isAI = verdict === "ai_generated";
  const isReal = verdict === "authentic";
  const color = isAI
    ? "text-signal-blood border-signal-blood/40 bg-signal-blood/5"
    : isReal
    ? "text-signal-sage border-signal-sage/40 bg-signal-sage/5"
    : "text-signal-amber border-signal-amber/40 bg-signal-amber/5";
  const label = isAI ? "AI Generated" : isReal ? "Authentic" : verdict?.replace("_", " ") || "Unknown";

  return (
    <span className={`font-mono text-[11px] uppercase tracking-[0.14em] border px-3 py-1 rounded-full ${color}`}>
      {label}
      {score !== null && ` - ${Math.round(score * 100)}%`}
    </span>
  );
}

export default function FeedDetailPage() {
  const { id } = useParams<{ id: string }>();

  const { data: item, isLoading, isError } = useQuery({
    queryKey: ["feed-detail", id],
    queryFn: () => feed.detail(id!).then((r) => r.data),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="animate-fade-in space-y-4">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-64 w-full rounded" />
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-4 w-1/4" />
      </div>
    );
  }

  if (isError || !item) {
    return (
      <div className="text-center py-20">
        <p className="text-ink-400 font-mono text-sm">Submission not found.</p>
        <Link to="/feed" className="mt-2 inline-block text-iris hover:text-iris-light underline text-sm">
          Back to feed
        </Link>
      </div>
    );
  }

  const isImage = item.mime_type?.startsWith("image/");

  return (
    <div>
      <div className="flex items-center gap-3 mb-6 font-mono text-[11px] uppercase tracking-[0.14em]">
        <Link to="/feed" className="flex items-center gap-1.5 text-ink-400 hover:text-ink-100 transition">
          <ArrowLeft size={13} strokeWidth={1.5} />
          Public Feed
        </Link>
        <span className="text-ink-700">/</span>
        <Globe size={12} strokeWidth={1.5} className="text-iris" />
        <span className="text-ink-500 truncate max-w-xs">{item.original_filename}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          {isImage && item.thumbnail_url && (
            <div className="case-card overflow-hidden">
              <img
                src={item.thumbnail_url}
                alt={item.original_filename}
                className="w-full max-h-[500px] object-contain bg-ink-950"
              />
            </div>
          )}

          {item.analysis_results.length > 0 && (
            <div className="case-card p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 mb-4">
                Analysis Results
              </div>
              <div className="space-y-3">
                {item.analysis_results.map((r) => (
                  <div key={r.id} className="flex items-center justify-between py-2 border-b border-ink-900 last:border-0">
                    <span className="font-mono text-[11px] text-ink-300 capitalize">
                      {r.analyzer_name.replace("_", " ")}
                    </span>
                    <div className="flex items-center gap-3">
                      <div className="w-24 h-1 bg-ink-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-iris rounded-full"
                          style={{ width: `${Math.round(r.confidence * 100)}%` }}
                        />
                      </div>
                      <span className="font-mono text-[10px] text-ink-400 w-12 text-right">
                        {Math.round(r.confidence * 100)}%
                      </span>
                      <span className={`font-mono text-[9px] uppercase tracking-[0.14em] w-20 text-right ${
                        r.verdict === "ai_generated"
                          ? "text-signal-blood"
                          : r.verdict === "authentic"
                          ? "text-signal-sage"
                          : "text-signal-amber"
                      }`}>
                        {r.verdict?.replace("_", " ")}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="case-card p-6">
            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 mb-4">
              Verdict
            </div>
            <VerdictBadge verdict={item.final_verdict} score={item.final_score} />
          </div>

          <div className="case-card p-6 space-y-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
              Submission Info
            </div>
            <div className="space-y-3">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-600 mb-1">
                  File
                </div>
                <div className="font-mono text-xs text-ink-300 break-all">
                  {item.original_filename}
                </div>
              </div>
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-600 mb-1">
                  Type
                </div>
                <div className="font-mono text-xs text-ink-300">{item.mime_type}</div>
              </div>
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-600 mb-1">
                  Size
                </div>
                <div className="font-mono text-xs text-ink-300">
                  {(item.file_size / 1024).toFixed(1)} KB
                </div>
              </div>
            </div>
          </div>

          <div className="case-card p-6 space-y-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
              Submitted by
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-ink-800 border border-ink-700 flex items-center justify-center">
                <User size={14} strokeWidth={1.5} className="text-ink-500" />
              </div>
              <div>
                <div className="font-mono text-xs text-ink-200">{item.uploader.username}</div>
                <div className="font-mono text-[10px] text-ink-600 flex items-center gap-1 mt-0.5">
                  <Calendar size={9} strokeWidth={1.5} />
                  Joined {new Date(item.uploader.date_joined).getFullYear()}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-ink-600 mt-2">
              <Calendar size={11} strokeWidth={1.5} />
              <span className="font-mono text-[10px]">
                {new Date(item.created_at).toLocaleDateString("en-GB", {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
