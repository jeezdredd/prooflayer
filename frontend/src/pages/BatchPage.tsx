import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { batches } from "../api/endpoints";
import type { BatchDetail } from "../types";
import { toast } from "../components/ui/Toast";

const VERDICT_CLASS: Record<string, string> = {
  fake: "text-signal-blood",
  likely_fake: "text-signal-blood",
  suspicious: "text-signal-amber",
  needs_review: "text-signal-amber",
  authentic: "text-signal-sage",
  authentic_edited: "text-signal-sage",
};

const FLAG_ORDER = ["fake", "likely_fake", "suspicious", "needs_review", "inconclusive", "authentic_edited", "authentic", ""];

export default function BatchPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery<BatchDetail>({
    queryKey: ["batch", id],
    queryFn: () => batches.detail(id!).then((r) => r.data),
    enabled: !!id,
    refetchInterval: (q) => {
      const d = q.state.data;
      return d && d.summary.done >= d.summary.total ? false : 3000;
    },
  });

  const download = async () => {
    try {
      const res = await batches.exportCsv(id!);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `prooflayer_batch_${id}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Export failed");
    }
  };

  if (isLoading || !data) return <p className="text-ink-500">Loading batch…</p>;

  const { summary } = data;
  const items = [...data.items].sort(
    (a, b) => FLAG_ORDER.indexOf(a.final_verdict) - FLAG_ORDER.indexOf(b.final_verdict) || (b.final_score ?? 0) - (a.final_score ?? 0),
  );
  const pct = summary.total ? Math.round((summary.done / summary.total) * 100) : 0;

  return (
    <div>
      <div className="flex items-end justify-between flex-wrap gap-4 mb-6">
        <div>
          <span className="label-mono">Batch</span>
          <h1 className="font-display text-4xl text-white mt-2">{data.name || "Untitled batch"}</h1>
          <p className="font-mono text-[11px] text-ink-500 mt-2">
            {summary.done}/{summary.total} analysed
            {Object.entries(summary.by_verdict).map(([v, n]) => ` · ${n} ${v.replace("_", " ")}`)}
          </p>
        </div>
        <button type="button" onClick={download}
          className="flex items-center gap-2 border border-[var(--line-strong)] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-300 hover:text-signal-amber hover:border-signal-amber/50">
          <Download size={13} /> CSV
        </button>
      </div>

      <div className="h-px bg-[var(--line-strong)] mb-6 relative overflow-hidden">
        <div className="absolute inset-y-0 left-0 bg-signal-amber transition-all duration-700" style={{ width: `${pct}%` }} />
      </div>

      <div className="divide-y divide-[var(--line-strong)]">
        {items.map((it) => (
          <Link key={it.id} to={`/results/${it.id}`}
            className="grid grid-cols-[1fr_auto] md:grid-cols-12 gap-3 items-center py-3 hover:bg-ink-800/40 px-2 -mx-2 transition-colors">
            <span className="md:col-span-6 text-ink-100 truncate">{it.original_filename}</span>
            <span className="md:col-span-2 font-mono text-[11px] text-ink-500 hidden md:block">{it.mime_type}</span>
            <span className={`md:col-span-2 font-mono text-[11px] uppercase tracking-[0.12em] ${VERDICT_CLASS[it.final_verdict] || "text-ink-400"}`}>
              {it.status === "completed" ? it.final_verdict.replace("_", " ") || "-" : it.status}
            </span>
            <span className="md:col-span-2 font-mono text-[11px] text-ink-400 text-right hidden md:block">
              {it.final_score != null ? `${Math.round(it.final_score * 100)}%` : ""}
            </span>
          </Link>
        ))}
      </div>

      {data.skipped.length > 0 && (
        <div className="mt-8">
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-2">Skipped</div>
          {data.skipped.map((s, i) => (
            <p key={i} className="font-mono text-[11px] text-ink-400">{s.name} - {s.reason}</p>
          ))}
        </div>
      )}
    </div>
  );
}
