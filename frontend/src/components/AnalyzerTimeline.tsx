import clsx from "clsx";
import { useEffect, useState } from "react";
import type { AnalysisResult, ExpectedAnalyzer, Submission } from "../types";

const ANALYZER_LABELS: Record<string, string> = {
  metadata: "Metadata · EXIF",
  ela: "Error Level Analysis",
  ai_detector: "AI Image Ensemble",
  llm_vision: "Vision LLM",
  video_frame: "Video Frame Analysis",
  audio_spectrogram: "Audio Spectrogram",
  llm_text: "Text LLM",
  community_forensics: "Community Forensics · ViT",
  npr_detector: "NPR Detector · ViT",
  siglip_detector: "SigLIP Detector",
  custom_detector: "ProofLayer Detector",
};

const ANALYZER_CODE: Record<string, string> = {
  metadata: "META",
  ela: "ELA",
  ai_detector: "AI-3",
  llm_vision: "VLM",
  video_frame: "VID",
  audio_spectrogram: "AUD",
  llm_text: "TXT",
  community_forensics: "CF",
  npr_detector: "NPR",
  siglip_detector: "SIGL",
  custom_detector: "PL",
};

const ANALYZER_WEIGHTS: Record<string, number> = {
  metadata: 1,
  ela: 2,
  ai_detector: 20,
  llm_vision: 25,
  video_frame: 30,
  audio_spectrogram: 8,
  llm_text: 6,
  community_forensics: 20,
  npr_detector: 15,
  siglip_detector: 15,
  custom_detector: 20,
};

const ANALYZER_ETA_SECS: Record<string, number> = {
  metadata: 3,
  ela: 5,
  community_forensics: 60,
  llm_vision: 45,
  video_frame: 40,
  audio_spectrogram: 15,
  llm_text: 20,
  npr_detector: 30,
  siglip_detector: 25,
  ai_detector: 25,
  custom_detector: 20,
};

const VERDICT_TONE: Record<string, { color: string; bg: string; label: string }> = {
  authentic: { color: "text-signal-sage", bg: "bg-signal-sage/10 border-signal-sage/30", label: "Authentic" },
  suspicious: { color: "text-signal-amber", bg: "bg-signal-amber/10 border-signal-amber/30", label: "Suspicious" },
  fake: { color: "text-signal-blood", bg: "bg-signal-blood/10 border-signal-blood/30", label: "Fake" },
  inconclusive: { color: "text-ink-400", bg: "bg-ink-800 border-ink-500", label: "Inconclusive" },
  error: { color: "text-signal-blood/70", bg: "bg-signal-blood/5 border-signal-blood/30", label: "Error" },
};

interface Step {
  name: string;
  description: string;
  result?: AnalysisResult;
  state: "done" | "running" | "pending" | "skipped";
}

function buildSteps(submission: Submission, runningAnalyzers?: Set<string>): Step[] {
  const expected: ExpectedAnalyzer[] = submission.expected_analyzers || [];
  const isProcessing = submission.status === "processing" || submission.status === "pending";
  const isFailed = submission.status === "failed";

  const sources: Step[] = expected.map((a) => {
    const result = submission.analysis_results.find((r) => r.analyzer_name === a.name);
    let state: Step["state"];
    if (result) state = "done";
    else if (isProcessing) {
      if (runningAnalyzers && runningAnalyzers.size > 0) {
        state = runningAnalyzers.has(a.name) ? "running" : "pending";
      } else {
        state = "pending";
      }
    } else if (isFailed) state = "skipped";
    else state = "skipped";
    return { name: a.name, description: a.description, result, state };
  });

  if (sources.length === 0) {
    return submission.analysis_results.map((r) => ({
      name: r.analyzer_name,
      description: "",
      result: r,
      state: "done" as const,
    }));
  }

  if (isProcessing && (!runningAnalyzers || runningAnalyzers.size === 0)) {
    const msg = (submission.status_message || "").toLowerCase();
    const msgMatchIdx = msg
      ? sources.findIndex(
          (s) =>
            s.state === "pending" &&
            (msg.includes(s.name.toLowerCase()) || msg.includes(s.name.replace(/_/g, " ").toLowerCase()))
        )
      : -1;
    const targetIdx = msgMatchIdx >= 0 ? msgMatchIdx : sources.findIndex((s) => s.state === "pending");
    if (targetIdx >= 0) sources[targetIdx].state = "running";
  }

  return sources;
}

function useElapsed(active: boolean) {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    if (!active) return;
    setSecs(0);
    const start = Date.now();
    const id = setInterval(() => setSecs((Date.now() - start) / 1000), 100);
    return () => clearInterval(id);
  }, [active]);
  return secs;
}

function StateMarker({ state, verdict }: { state: Step["state"]; verdict: string }) {
  if (state === "done") {
    const tone = VERDICT_TONE[verdict] || VERDICT_TONE.inconclusive;
    const sym =
      verdict === "authentic" ? "✓" : verdict === "fake" || verdict === "suspicious" ? "!" : verdict === "error" ? "×" : "-";
    return (
      <div className={clsx("w-7 h-7 border flex items-center justify-center text-sm font-bold animate-check-pop", tone.color, tone.bg)}>
        {sym}
      </div>
    );
  }
  if (state === "running") {
    return (
      <div className="w-7 h-7 border border-signal-amber bg-signal-amber/10 flex items-center justify-center relative">
        <span className="w-2 h-2 bg-signal-amber pulse-dot text-signal-amber" />
      </div>
    );
  }
  if (state === "skipped") {
    return (
      <div className="w-7 h-7 border border-ink-700 bg-ink-850 flex items-center justify-center text-ink-500 text-sm">
        ×
      </div>
    );
  }
  return (
    <div className="w-7 h-7 border border-dashed border-ink-600 flex items-center justify-center">
      <div className="w-1 h-1 bg-ink-500" />
    </div>
  );
}

function AnalyzerRow({ step, isLast, index }: { step: Step; isLast: boolean; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const label = ANALYZER_LABELS[step.name] || step.name;
  const code = ANALYZER_CODE[step.name] || step.name.slice(0, 4).toUpperCase();
  const verdict = step.result?.verdict || "";
  const tone = VERDICT_TONE[verdict] || VERDICT_TONE.inconclusive;
  const elapsed = useElapsed(step.state === "running");
  const expectedSecs = ANALYZER_ETA_SECS[step.name] || 15;

  return (
    <div className={clsx("relative flex gap-4 animate-fade-in-up", !isLast && "pb-5")}>
      {/* Vertical thread */}
      {!isLast && (
        <div className="absolute left-[14px] top-7 bottom-0 w-px bg-gradient-to-b from-ink-700 via-ink-700 to-transparent" />
      )}

      <div className="relative shrink-0 z-10">
        <StateMarker state={step.state} verdict={verdict} />
      </div>

      <div className="flex-1 min-w-0">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="w-full text-left group"
          aria-expanded={expanded}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 ticker">
                #{String(index + 1).padStart(2, "0")} · {code}
              </span>
              <span className="text-ink-700">/</span>
              <span className="font-display text-lg text-ink-50 group-hover:text-signal-amber transition-colors leading-none">
                {label}
              </span>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              {step.result?.execution_time != null && (
                <span className="font-mono text-[10px] text-ink-500 ticker">
                  {step.result.execution_time.toFixed(1)}s
                </span>
              )}
              {step.state === "running" && (
                <span className="font-mono text-[10px] text-signal-amber ticker animate-pulse-soft">
                  {elapsed.toFixed(1)}s
                </span>
              )}
              {step.result && (
                <>
                  <span className="font-mono text-xs text-ink-200 ticker w-10 text-right">
                    {Math.round(step.result.confidence * 100)}%
                  </span>
                  <span className={clsx("badge", tone.color, "border-current")}>
                    {tone.label}
                  </span>
                </>
              )}
              {step.state === "running" && (
                <span className="badge text-signal-amber border-current">
                  Running
                </span>
              )}
              {step.state === "pending" && (
                <span className="badge text-ink-500 border-ink-700">
                  Queued
                </span>
              )}
              {step.state === "skipped" && (
                <span className="badge text-ink-500 border-ink-700">
                  Skipped
                </span>
              )}
            </div>
          </div>

          {/* Per-analyzer progress */}
          {step.state === "running" && (
            <div className="mt-3 ml-0">
              <div className="relative h-px bg-ink-800 overflow-hidden">
                <div
                  className="absolute inset-y-0 left-0 bg-signal-amber transition-all duration-300"
                  style={{ width: `${elapsed < expectedSecs ? Math.min(95, (elapsed / expectedSecs) * 100) : 95}%` }}
                />
                <div className="absolute inset-0 stripe-active" />
              </div>
              <div className="mt-1 flex justify-between text-[10px] font-mono text-ink-500">
                <span>est ~{expectedSecs}s</span>
                <span className="text-signal-amber animate-pulse-soft">
                  {elapsed < expectedSecs
                    ? `${(expectedSecs - elapsed).toFixed(1)}s remaining`
                    : elapsed > expectedSecs * 2
                    ? `loading model... ${elapsed.toFixed(0)}s`
                    : `still working... ${elapsed.toFixed(0)}s`}
                </span>
              </div>
            </div>
          )}
        </button>

        {expanded && (
          <div className="mt-3 pl-0 animate-fade-in-up">
            {step.description && (
              <p className="text-sm text-ink-300 leading-relaxed mb-3">
                {step.description}
              </p>
            )}
            {step.result?.error_message && (
              <div className="text-xs text-signal-blood font-mono mb-2">
                ERROR: {step.result.error_message}
              </div>
            )}
            {step.result && Object.keys(step.result.evidence || {}).length > 0 && (
              <div className="bg-ink-950 border border-ink-700 p-3 relative">
                <div className="absolute top-2 right-2 font-mono text-[9px] uppercase tracking-[0.16em] text-ink-600">
                  Evidence
                </div>
                <pre className="font-mono text-[11px] text-ink-200 overflow-x-auto overflow-y-auto max-h-52 whitespace-pre-wrap leading-relaxed">
                  {JSON.stringify(
                    Object.fromEntries(
                      Object.entries(step.result.evidence).filter(([k]) => k !== "heatmap_url")
                    ),
                    null, 2
                  )}
                </pre>
              </div>
            )}
            {typeof step.result?.evidence?.heatmap_url === "string" && (
              <ELAHeatmapOverlay heatmapUrl={step.result.evidence.heatmap_url} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ELAHeatmapOverlay({ heatmapUrl }: { heatmapUrl: string }) {
  const [opacity, setOpacity] = useState(60);
  const apiBase = import.meta.env.VITE_API_URL?.replace("/api/v1", "") || "";
  const fullUrl = heatmapUrl.startsWith("http") ? heatmapUrl : `${apiBase}${heatmapUrl}`;

  return (
    <div className="mt-3 bg-ink-950 border border-ink-700 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500">ELA Heatmap</span>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[9px] text-ink-600">opacity</span>
          <input
            type="range"
            min={0}
            max={100}
            value={opacity}
            onChange={(e) => setOpacity(Number(e.target.value))}
            className="w-20 accent-signal-amber"
          />
          <span className="font-mono text-[9px] text-ink-400 w-8">{opacity}%</span>
        </div>
      </div>
      <img
        src={fullUrl}
        alt="ELA heatmap"
        className="max-h-72 max-w-full object-contain border border-ink-700"
        style={{ opacity: opacity / 100 }}
      />
      <p className="font-mono text-[9px] text-ink-600 mt-2">
        Bright red = high error level = possible manipulation. Uniform areas suggest authentic regions.
      </p>
    </div>
  );
}

export default function AnalyzerTimeline({ submission, runningAnalyzers }: { submission: Submission; runningAnalyzers?: Set<string> }) {
  const steps = buildSteps(submission, runningAnalyzers);
  if (steps.length === 0) return null;

  const doneCount = steps.filter((s) => s.state === "done").length;
  const skippedCount = steps.filter((s) => s.state === "skipped").length;
  const errorCount = steps.filter((s) => s.result?.verdict === "error").length;
  const totalCount = steps.length;
  const isProcessing = submission.status === "processing" || submission.status === "pending";
  const hasIncompleteResults = !isProcessing && (skippedCount > 0 || errorCount > 0);

  const totalWeight = steps.reduce((acc, s) => acc + (ANALYZER_WEIGHTS[s.name] || 5), 0);
  const doneWeight = steps
    .filter((s) => s.state === "done" || s.state === "skipped")
    .reduce((acc, s) => acc + (ANALYZER_WEIGHTS[s.name] || 5), 0);
  const overallPct = totalWeight > 0 ? Math.min(100, (doneWeight / totalWeight) * 100) : 0;

  const remainingSecs = steps
    .filter((s) => s.state === "pending" || s.state === "running")
    .reduce((acc, s) => acc + (ANALYZER_ETA_SECS[s.name] || 15), 0);

  return (
    <div>
      {/* Section header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="label-mono">Analyzer Pipeline</span>
          <span className="text-ink-700">/</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400 ticker">
            {String(doneCount).padStart(2, "0")}<span className="text-ink-600">·</span>{String(totalCount).padStart(2, "0")} {isProcessing ? "RUNNING" : "COMPLETE"}
            {skippedCount > 0 && <span className="text-ink-600 ml-2">{skippedCount} SKIPPED</span>}
          </span>
        </div>
        <div className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.14em]">
          <span className="ticker text-ink-200">{Math.round(overallPct)}%</span>
          {isProcessing && remainingSecs > 0 && (
            <span className="text-signal-amber ticker">~{remainingSecs}S LEFT</span>
          )}
        </div>
      </div>

      {/* Overall bar */}
      <div className="relative h-1 bg-ink-800 mb-6 overflow-hidden">
        <div
          className={clsx(
            "absolute inset-y-0 left-0 transition-all duration-500 ease-out",
            isProcessing ? "bg-signal-amber" : "bg-signal-sage",
          )}
          style={{ width: `${overallPct}%` }}
        />
        {isProcessing && (
          <div
            className="absolute inset-y-0 h-full w-1/4 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-scan-bar"
          />
        )}
      </div>

      {/* Status message */}
      {isProcessing && (
        <div className="mb-6 px-3 py-2 border-l-2 border-signal-amber bg-signal-amber/5">
          {(() => {
            const running = steps.filter((s) => s.state === "running");
            if (running.length > 1) {
              return (
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  {running.map((s) => (
                    <span key={s.name} className="flex items-center gap-1.5 font-mono text-[11px] text-ink-200">
                      <span className="w-1.5 h-1.5 rounded-full bg-signal-amber pulse-dot" />
                      {ANALYZER_LABELS[s.name] || s.name}
                    </span>
                  ))}
                </div>
              );
            }
            if (running.length === 1) {
              return (
                <span className="flex items-center gap-2 font-mono text-[11px] text-ink-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-signal-amber pulse-dot" />
                  Running {ANALYZER_LABELS[running[0].name] || running[0].name}...
                </span>
              );
            }
            return (
              <span className="flex items-center gap-2 font-mono text-[11px] text-ink-200">
                <span className="w-1.5 h-1.5 rounded-full bg-signal-amber pulse-dot" />
                {submission.status_message || "Processing..."}
              </span>
            );
          })()}
        </div>
      )}

      {/* All skipped = worker never ran */}
      {!isProcessing && doneCount === 0 && skippedCount === totalCount && totalCount > 0 && (
        <div className="mb-6 flex items-start gap-3 px-3 py-2.5 border-l-2 border-signal-blood/60 bg-signal-blood/5">
          <span className="mt-0.5 text-signal-blood text-[13px]">!</span>
          <span className="font-mono text-[11px] text-ink-300 leading-relaxed">
            Background worker did not process this submission. Celery may be down or the task crashed before startup. Check worker logs and re-upload to retry.
          </span>
        </div>
      )}

      {/* Partial incomplete warning */}
      {hasIncompleteResults && !(doneCount === 0 && skippedCount === totalCount) && (
        <div className="mb-6 flex items-start gap-3 px-3 py-2.5 border-l-2 border-signal-amber/60 bg-signal-amber/5">
          <span className="mt-0.5 text-signal-amber text-[13px]">⚠</span>
          <span className="font-mono text-[11px] text-ink-300 leading-relaxed">
            Some analyzers did not complete ({skippedCount > 0 && `${skippedCount} skipped`}{skippedCount > 0 && errorCount > 0 && ", "}{errorCount > 0 && `${errorCount} failed`}). Final verdict may be inaccurate.
          </span>
        </div>
      )}

      {/* Steps */}
      <div className="space-y-1">
        {steps.map((step, i) => (
          <AnalyzerRow key={step.name} step={step} isLast={i === steps.length - 1} index={i} />
        ))}
      </div>
    </div>
  );
}
