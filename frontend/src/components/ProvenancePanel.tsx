import { Link } from "react-router-dom";
import { useProvenance } from "../hooks/useProvenance";

const SOURCE_LABELS: Record<string, string> = {
  phash_match: "Near-Duplicate (pHash)",
  clip_neighbour: "Semantic Neighbour (CLIP)",
  tineye: "TinEye",
  google_vision: "Google Vision",
  c2pa: "C2PA Credentials",
};

const SOURCE_COLORS: Record<string, string> = {
  phash_match: "bg-iris/10 text-iris-light border-iris/40",
  clip_neighbour: "bg-signal-violet/10 text-signal-violet border-signal-violet/40",
  tineye: "bg-signal-violet/10 text-signal-violet border-signal-violet/40",
  google_vision: "bg-iris/10 text-iris-light border-iris/40",
  c2pa: "bg-sage-500/10 text-sage-300 border-sage-500/40",
};

interface ProvenancePanelProps {
  submissionId: string;
}

function neighbourSubmissionId(raw: Record<string, unknown> | null): string | null {
  if (!raw) return null;
  const v = raw["submission_id"];
  return typeof v === "string" ? v : null;
}

export default function ProvenancePanel({ submissionId }: ProvenancePanelProps) {
  const { data: results, isLoading } = useProvenance(submissionId);

  if (isLoading) {
    return (
      <div className="case-card p-6 mt-4">
        <h4 className="label-mono mb-3">Provenance</h4>
        <p className="font-mono text-xs text-ink-500">Checking sources...</p>
      </div>
    );
  }

  return (
    <div className="case-card p-6 mt-4">
      <h4 className="label-mono mb-3">Provenance</h4>

      {!results || results.length === 0 ? (
        <p className="font-mono text-xs text-ink-500">No matches found in external sources or local index.</p>
      ) : (
        <div className="space-y-3">
          {results.map((r) => {
            const neighbourId = neighbourSubmissionId(r.raw_data as Record<string, unknown> | null);
            const cosine = typeof (r.raw_data as Record<string, unknown> | null)?.["cosine_distance"] === "number"
              ? ((r.raw_data as Record<string, number>).cosine_distance).toFixed(3)
              : null;
            return (
              <div key={r.id} className="flex items-start justify-between gap-3 p-3 bg-ink-950/60 border border-ink-800">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span
                      className={`font-mono text-[10px] uppercase tracking-[0.12em] px-2 py-0.5 border ${SOURCE_COLORS[r.source_type] ?? "bg-ink-900 text-ink-300 border-ink-700"}`}
                    >
                      {SOURCE_LABELS[r.source_type] ?? r.source_type}
                    </span>
                    {r.similarity_score !== null && (
                      <span className="font-mono text-[10px] text-ink-400 tabular-nums">
                        {(r.similarity_score * 100).toFixed(0)}% sim
                      </span>
                    )}
                    {cosine !== null && (
                      <span className="font-mono text-[10px] text-ink-500 tabular-nums">
                        cosine {cosine}
                      </span>
                    )}
                  </div>
                  {r.title && (
                    <p className="text-sm text-ink-200 truncate">{r.title}</p>
                  )}
                  {neighbourId && (
                    <Link
                      to={`/results/${neighbourId}`}
                      className="text-xs text-iris hover:text-iris-light transition font-mono"
                    >
                      view neighbour ->
                    </Link>
                  )}
                  {r.source_url && (
                    <a
                      href={r.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-iris hover:text-iris-light truncate block transition"
                    >
                      {r.source_url}
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
