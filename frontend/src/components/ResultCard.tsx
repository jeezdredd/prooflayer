import clsx from "clsx";
import type { Submission } from "../types";
import AnalyzerTimeline from "./AnalyzerTimeline";

interface ResultCardProps {
  submission: Submission;
}

const VERDICT_TONE: Record<string, { color: string; label: string; ring: string; sub?: string }> = {
  authentic: { color: "text-signal-sage", ring: "border-signal-sage/40", label: "REAL" },
  authentic_edited: { color: "text-signal-amber", ring: "border-signal-amber/40", label: "REAL · EDITED", sub: "Image appears genuine but shows signs of digital editing or compositing." },
  suspicious: { color: "text-signal-amber", ring: "border-signal-amber/40", label: "Suspicious" },
  likely_fake: { color: "text-signal-blood", ring: "border-signal-blood/40", label: "Likely AI" },
  fake: { color: "text-signal-blood", ring: "border-signal-blood/60", label: "AI" },
  needs_review: { color: "text-signal-violet", ring: "border-signal-violet/40", label: "Needs Review" },
  inconclusive: { color: "text-ink-300", ring: "border-ink-600", label: "Inconclusive" },
};

function riskLevel(score: number): { label: string; color: string } {
  if (score < 0.35) return { label: "LOW", color: "text-signal-sage" };
  if (score < 0.65) return { label: "MED", color: "text-signal-amber" };
  return { label: "HIGH", color: "text-signal-blood" };
}

function shortHash(hash: string | undefined) {
  if (!hash) return "-";
  return `${hash.slice(0, 8)}…${hash.slice(-6)}`;
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

export default function ResultCard({ submission }: ResultCardProps) {
  const verdict = VERDICT_TONE[submission.final_verdict] || VERDICT_TONE.inconclusive;
  const score = submission.final_score;
  const isProcessing = submission.status === "processing" || submission.status === "pending";

  return (
    <article className="case-card crop-marks animate-rise">
      {/* Header strip: case ID, timestamp, verdict */}
      <header className="flex items-stretch border-b border-ink-700">
        <div className="flex-1 px-4 sm:px-6 py-4 sm:py-5">
          <div className="flex items-center gap-3 mb-3">
            <span className="label-mono">Evidence File</span>
            <span className="font-mono text-[10px] text-ink-500">/</span>
            <span className="font-mono text-[10px] text-ink-400 ticker">
              {submission.id.slice(0, 8).toUpperCase()}
            </span>
          </div>
          <h2 className="font-display text-2xl sm:text-3xl text-ink-50 leading-tight break-all">
            {submission.original_filename}
          </h2>
          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 font-mono text-[11px] text-ink-400">
            <span><span className="text-ink-600">type:</span> {submission.mime_type || "unknown"}</span>
            <span><span className="text-ink-600">size:</span> {formatSize(submission.file_size)}</span>
            <span><span className="text-ink-600">sha256:</span> <span className="ticker">{shortHash(submission.sha256_hash)}</span></span>
          </div>
        </div>

        <div className="reg-tick" />

        <div className="px-4 sm:px-6 py-4 sm:py-5 flex flex-col items-end justify-between min-w-[110px] sm:min-w-[180px]">
          <span className={clsx("badge", verdict.color, verdict.ring)}>
            <span className="w-1 h-1 bg-current rounded-full" />
            {verdict.label}
          </span>
          {score !== null && score !== undefined && (
            <div className="text-right mt-2">
              <div className={clsx("font-display text-4xl sm:text-5xl leading-none ticker", riskLevel(score).color)}>
                {riskLevel(score).label}
              </div>
              <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mt-1">
                {Math.round(score * 100)}% · Risk level
              </div>
            </div>
          )}
          {isProcessing && (
            <div className="text-right mt-2">
              <div className="font-display text-2xl text-signal-amber italic">analyzing…</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mt-1">
                Awaiting verdict
              </div>
            </div>
          )}
        </div>
      </header>

      {verdict.sub && (
        <div className="px-6 py-2.5 border-b border-ink-700 bg-signal-amber/5 flex items-center gap-2.5">
          <span className="w-1 h-1 rounded-full bg-signal-amber shrink-0" />
          <span className="font-mono text-[11px] text-signal-amber">{verdict.sub}</span>
        </div>
      )}

      {/* Score bar */}
      {score !== null && score !== undefined && (
        <div className="px-6 py-3 border-b border-ink-700">
          <div className="flex justify-between mb-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
            <span>Authentic</span>
            <span>Fake</span>
          </div>
          <div className="relative h-2 bg-ink-800">
            <div className="absolute inset-y-0 left-0 w-[30%] bg-signal-sage/15" />
            <div className="absolute inset-y-0 left-[30%] w-[20%] bg-signal-amber/15" />
            <div className="absolute inset-y-0 left-[50%] w-[20%] bg-signal-amber/20" />
            <div className="absolute inset-y-0 left-[70%] right-0 bg-signal-blood/15" />
            <div
              className="absolute -top-1 -bottom-1 w-0.5 bg-ink-50 shadow-[0_0_12px_rgba(255,255,255,0.6)]"
              style={{ left: `${score * 100}%`, transform: "translateX(-1px)" }}
            />
          </div>
        </div>
      )}

      {/* Known fake banner */}
      {submission.is_known_fake && (
        <div className="px-6 py-3 border-b border-ink-700 bg-signal-blood/5 flex items-center gap-3">
          <span className="w-6 h-6 border border-signal-blood text-signal-blood text-xs flex items-center justify-center font-bold">!</span>
          <div className="flex-1">
            <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-signal-blood">Known fake match</div>
            <div className="text-sm text-ink-200">SHA-256 found in known-fake registry. High confidence forgery.</div>
          </div>
        </div>
      )}

      {/* Image preview */}
      {submission.file_url && submission.mime_type?.startsWith("image/") && (
        <div className="px-6 py-4 border-b border-ink-700">
          <img
            src={submission.file_url}
            alt={submission.original_filename}
            className="max-h-64 max-w-full object-contain border border-ink-700"
            loading="lazy"
            onError={(e) => {
              e.currentTarget.parentElement?.style.setProperty("display", "none");
            }}
          />
        </div>
      )}

      {/* Pipeline */}
      <div className="px-6 py-6">
        <AnalyzerTimeline submission={submission} />
      </div>
    </article>
  );
}
