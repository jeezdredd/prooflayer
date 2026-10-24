import clsx from "clsx";
import { useEffect, useState } from "react";
import type { AnalysisResult, ExpectedAnalyzer, Submission } from "../types";
import { msg, t } from "../i18n";
import { elaWorksOn, readableReasoning } from "./resultView";

export const ANALYZER_LABELS: Record<string, string> = {
  metadata: msg("Labels in the file"),
  ela: msg("Pasted-in pieces check"),
  ai_detector: msg("AI detector 2"),
  llm_vision: msg("Model that looks at the picture"),
  video_frame: msg("Video frames"),
  audio_spectrogram: msg("Voice check"),
  llm_text: msg("Language model"),
  text_classifier: msg("AI writing detector"),
  community_forensics: msg("AI detector 1"),
  npr_detector: msg("Noise detector"),
  siglip_detector: msg("Consistency detector"),
  custom_detector: msg("ProofLayer Detector"),
  clip_probe: msg("AI detector 3"),
  text_evasion: msg("Bypass Check"),
  text_grade_fit: msg("Age Fit"),
  text_style: msg("Style Consistency"),
  text_citations: msg("Ghost Citations"),
  text_genre: msg("Text Type"),
  text_shadow: msg("Assignment Shadow"),
};

const VOTE_WORDS: Record<string, string> = {
  fake: msg("for AI"),
  suspicious: msg("leans AI"),
  inconclusive: msg("not sure"),
  error: msg("did not run"),
};

const ANALYZER_CODE: Record<string, string> = {
  metadata: "META",
  ela: "ELA",
  ai_detector: "AI-3",
  llm_vision: "VLM",
  video_frame: "VID",
  audio_spectrogram: "AUD",
  llm_text: "TXT",
  text_classifier: "TXC",
  community_forensics: "CF",
  npr_detector: "NPR",
  siglip_detector: "SIGL",
  custom_detector: "PL",
  clip_probe: "CLIP",
  text_evasion: "BYP",
  text_grade_fit: "AGE",
  text_style: "STY",
  text_citations: "CIT",
  text_genre: "GEN",
  text_shadow: "SHD",
};

const ANALYZER_WEIGHTS: Record<string, number> = {
  metadata: 1,
  ela: 2,
  ai_detector: 20,
  llm_vision: 25,
  video_frame: 30,
  audio_spectrogram: 8,
  llm_text: 6,
  text_classifier: 6,
  community_forensics: 20,
  npr_detector: 15,
  siglip_detector: 15,
  custom_detector: 20,
  clip_probe: 5,
  text_evasion: 1,
  text_grade_fit: 2,
  text_style: 2,
  text_citations: 3,
  text_genre: 1,
  text_shadow: 2,
};

const ANALYZER_ETA_SECS: Record<string, number> = {
  metadata: 2,
  ela: 3,
  community_forensics: 15,
  llm_vision: 35,
  video_frame: 35,
  audio_spectrogram: 10,
  llm_text: 15,
  text_classifier: 5,
  npr_detector: 15,
  siglip_detector: 15,
  ai_detector: 20,
  custom_detector: 15,
  clip_probe: 3,
  text_evasion: 2,
  text_grade_fit: 3,
  text_style: 3,
  text_citations: 20,
  text_genre: 1,
  text_shadow: 4,
};

const VERDICT_TONE: Record<string, { color: string; bg: string; label: string }> = {
  authentic: { color: "text-signal-sage", bg: "bg-signal-sage/10 border-signal-sage/30", label: msg("Authentic") },
  suspicious: { color: "text-signal-amber", bg: "bg-signal-amber/10 border-signal-amber/30", label: msg("Suspicious") },
  fake: { color: "text-signal-blood", bg: "bg-signal-blood/10 border-signal-blood/30", label: msg("Fake") },
  inconclusive: { color: "text-ink-400", bg: "bg-ink-800 border-ink-500", label: msg("Inconclusive") },
  error: { color: "text-signal-blood/70", bg: "bg-signal-blood/5 border-signal-blood/30", label: msg("Error") },
};

export interface Step {
  name: string;
  description: string;
  result?: AnalysisResult;
  state: "done" | "running" | "pending" | "skipped";
}

export function buildSteps(submission: Submission, runningAnalyzers?: Set<string>): Step[] {
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
    const statusText = (submission.status_message || "").toLowerCase();
    const msgMatchIdx = statusText
      ? sources.findIndex(
          (s) =>
            s.state === "pending" &&
            (statusText.includes(s.name.toLowerCase()) || statusText.includes(s.name.replace(/_/g, " ").toLowerCase()))
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

const VERDICT_DOT: Record<string, string> = {
  authentic: "bg-signal-sage",
  suspicious: "bg-signal-amber",
  fake: "bg-signal-blood",
  inconclusive: "bg-ink-400",
  error: "bg-signal-blood/60",
};

function StateMarker({ state, verdict }: { state: Step["state"]; verdict: string }) {
  let dot;
  if (state === "done") dot = <span className={clsx("w-2 h-2 rounded-full animate-check-pop", VERDICT_DOT[verdict] || VERDICT_DOT.inconclusive)} />;
  else if (state === "running") dot = <span className="w-3 h-3 rounded-full border-[1.5px] border-signal-amber/25 border-t-signal-amber animate-spin" />;
  else if (state === "skipped") dot = <span className="w-2 h-2 rounded-full bg-ink-700" />;
  else dot = <span className="w-2 h-2 rounded-full border border-ink-600" />;
  return <div className="w-7 h-7 flex items-center justify-center">{dot}</div>;
}

function voteWord(step: Step, image: boolean): string {
  const result = step.result;
  if (!result) return "";
  if (step.name === "ela" && result.verdict !== "error") {
    if (!elaWorksOn(result.evidence ?? {})) return t("not for this format");
    return result.evidence?.manipulation_suspected === true ? t("may be edited") : t("no signs of editing");
  }
  if (result.verdict === "authentic") return image ? t("for a photo") : t("for a person");
  return t(VOTE_WORDS[result.verdict] ?? VOTE_WORDS.inconclusive);
}

function evidenceLines(step: Step): string[] {
  if (!step.result) return [];
  if (step.result.verdict === "error") return [t("This check could not run this time. The verdict was made without it.")];
  const ev = (step.result.evidence ?? {}) as Record<string, unknown>;
  const lines: string[] = [];
  if (step.name === "ela") {
    if (!elaWorksOn(ev)) lines.push(t("This check only works on JPEG photos, so it does not show editing in this file."));
    else if (ev.manipulation_suspected === true) lines.push(t("Some areas compress differently from the rest: they may have been pasted in. They are brighter on the map."));
    else lines.push(t("No signs of pasted-in pieces were found."));
  }
  const reasoning = step.name === "llm_vision" ? readableReasoning(ev) : null;
  if (reasoning) lines.push(t("What the model noticed: \"{reasoning}\"", { reasoning }));
  if (step.name === "metadata") {
    const camera = ev.camera as { has_camera_signature?: boolean; make?: string; model?: string } | undefined;
    if (camera?.has_camera_signature) lines.push(t("Camera recorded in the file: {name}", { name: [camera.make, camera.model].filter(Boolean).join(" ") }));
    if ((ev.metadata_presence as { stripped?: boolean } | undefined)?.stripped) {
      lines.push(t("The file has no camera data. That is normal after messengers and social networks."));
    }
    if ((ev.dates as { suspicious?: boolean } | undefined)?.suspicious) lines.push(t("The dates inside the file do not match each other."));
  }
  return lines;
}

function AnalyzerRow({ step, isLast, index, done, image, showRaw }: { step: Step; isLast: boolean; index: number; done: boolean; image: boolean; showRaw: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const label = ANALYZER_LABELS[step.name] ? t(ANALYZER_LABELS[step.name]) : step.name;
  const code = ANALYZER_CODE[step.name] || step.name.slice(0, 4).toUpperCase();
  const verdict = step.result?.verdict || "";
  const tone = VERDICT_TONE[verdict] || VERDICT_TONE.inconclusive;
  const elapsed = useElapsed(step.state === "running");
  const expectedSecs = ANALYZER_ETA_SECS[step.name] || 15;
  const lines = evidenceLines(step);
  const evidence = step.result?.evidence ?? {};
  const heatmap = typeof evidence.heatmap_url === "string" && elaWorksOn(evidence) ? evidence.heatmap_url : null;

  return (
    <div className={clsx("relative flex gap-4 animate-fade-in-up", !isLast && "pb-5")}>
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
              {!done && (
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 ticker">
                  #{String(index + 1).padStart(2, "0")} · {code}
                </span>
              )}
              <span className="font-display text-lg text-ink-50 group-hover:text-signal-amber transition-colors leading-none">
                {label}
              </span>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              {step.state === "running" && (
                <span className="font-mono text-[10px] text-signal-amber ticker animate-pulse-soft">
                  {t("{n} s", { n: elapsed.toFixed(1) })}
                </span>
              )}
              {step.result && (
                <span className={clsx("badge normal-case tracking-normal", tone.color, "border-current")}>
                  {voteWord(step, image)}
                </span>
              )}
              {step.state === "running" && (
                <span className="badge text-signal-amber border-current">
                  {t("Running")}
                </span>
              )}
              {step.state === "pending" && (
                <span className="badge text-ink-500 border-ink-700">
                  {t("Queued")}
                </span>
              )}
              {step.state === "skipped" && (
                <span className="badge text-ink-500 border-ink-700">
                  {t("Skipped")}
                </span>
              )}
            </div>
          </div>

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
                <span>{t("est ~{n}s", { n: expectedSecs })}</span>
                <span className="text-signal-amber animate-pulse-soft">
                  {elapsed < expectedSecs
                    ? t("{n}s remaining", { n: (expectedSecs - elapsed).toFixed(1) })
                    : elapsed > expectedSecs * 2
                    ? t("loading model... {n}s", { n: elapsed.toFixed(0) })
                    : t("still working... {n}s", { n: elapsed.toFixed(0) })}
                </span>
              </div>
            </div>
          )}
        </button>

        {expanded && (
          <div className="mt-3 pl-0 animate-fade-in-up">
            {step.description && (
              <p className="text-sm text-ink-300 leading-relaxed mb-3">
                {t(step.description)}
              </p>
            )}
            {lines.map((line) => (
              <p key={line} className="text-sm text-ink-100 leading-relaxed mb-2">{line}</p>
            ))}
            {showRaw && step.result?.error_message && (
              <div className="text-xs text-signal-blood font-mono mb-2">
                {step.result.error_message}
              </div>
            )}
            {showRaw && step.result && Object.keys(step.result.evidence || {}).length > 0 && (
              <div className="bg-ink-950 border border-ink-700 p-3 relative">
                <div className="absolute top-2 right-2 font-mono text-[9px] uppercase tracking-[0.16em] text-ink-600">
                  {t("Raw data for staff")}
                </div>
                <pre className="font-mono text-[11px] text-ink-200 overflow-x-auto overflow-y-auto max-h-52 whitespace-pre-wrap leading-relaxed">
                  {JSON.stringify(
                    Object.fromEntries(
                      Object.entries(step.result.evidence).filter(([k]) => k !== "heatmap_url" && k !== "heatmap_path")
                    ),
                    null, 2
                  )}
                </pre>
              </div>
            )}
            {heatmap && (
              <ELAHeatmapOverlay heatmapUrl={heatmap} suspected={evidence.manipulation_suspected === true} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ELAHeatmapOverlay({ heatmapUrl, suspected }: { heatmapUrl: string; suspected: boolean }) {
  const [opacity, setOpacity] = useState(60);
  const apiBase = import.meta.env.VITE_API_URL?.replace("/api/v1", "") || "";
  const fullUrl = heatmapUrl.startsWith("http") ? heatmapUrl : `${apiBase}${heatmapUrl}`;

  return (
    <div className="mt-3 bg-ink-950 border border-ink-700 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500">{t("Editing map")}</span>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[9px] text-ink-600">{t("opacity")}</span>
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
        alt={t("Editing map")}
        className="max-h-72 max-w-full object-contain border border-ink-700"
        style={{ opacity: opacity / 100 }}
      />
      <p className="text-xs text-ink-400 mt-2">
        {suspected
          ? t("The brightest areas compress differently from the rest of the picture: they may have been pasted in.")
          : t("The map is scaled to its brightest spot, so some red is always there. The check found no area that stands out.")}
      </p>
    </div>
  );
}

export default function AnalyzerTimeline({ submission, runningAnalyzers, showRaw = false }: { submission: Submission; runningAnalyzers?: Set<string>; showRaw?: boolean }) {
  const steps = buildSteps(submission, runningAnalyzers);
  if (steps.length === 0) return null;
  const image = !!submission.mime_type?.startsWith("image/");
  const proof = submission.analysis_results.some((r) => r.analyzer_name === "metadata" && r.evidence?.provenance_proof === true);

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

  const pendingEtas = steps
    .filter((s) => s.state === "pending" || s.state === "running")
    .map((s) => ANALYZER_ETA_SECS[s.name] || 15);
  const remainingSecs = pendingEtas.length > 0 ? Math.max(...pendingEtas) : 0;

  return (
    <div>
      {isProcessing ? (
        <>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="label-mono">{t("Analyzer Pipeline")}</span>
              <span className="text-ink-700">/</span>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400 ticker">
                {String(doneCount).padStart(2, "0")}<span className="text-ink-600">·</span>{String(totalCount).padStart(2, "0")} {t("RUNNING")}
              </span>
            </div>
            <div className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.14em]">
              <span className="ticker text-ink-200">{Math.round(overallPct)}%</span>
              {remainingSecs > 0 && (
                <span className="text-signal-amber ticker">{t("~{n}S LEFT", { n: remainingSecs })}</span>
              )}
            </div>
          </div>
          <div className="relative h-1 bg-ink-800 mb-6 overflow-hidden">
            <div className="absolute inset-y-0 left-0 transition-all duration-500 ease-out bg-signal-amber" style={{ width: `${overallPct}%` }} />
            <div className="absolute inset-y-0 h-full w-1/4 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-scan-bar" />
          </div>
        </>
      ) : (
        <div className="mb-4">
          <span className="label-mono">{t("How each check voted")}</span>
          <p className="text-xs text-ink-500 mt-1">{t("Click a check to see what it looks at and what it found.")}</p>
        </div>
      )}

      {!isProcessing && proof && (
        <div className="mb-6 px-3 py-2.5 border-l-2 border-signal-blood/60 bg-signal-blood/5 text-sm text-ink-200 leading-relaxed">
          {t("The AI mark in the file outweighs the detector votes: even if a detector voted \"for a photo\", the conclusion does not change.")}
        </div>
      )}

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
                      {ANALYZER_LABELS[s.name] ? t(ANALYZER_LABELS[s.name]) : s.name}
                    </span>
                  ))}
                </div>
              );
            }
            if (running.length === 1) {
              return (
                <span className="flex items-center gap-2 font-mono text-[11px] text-ink-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-signal-amber pulse-dot" />
                  {t("Running {name}...", { name: ANALYZER_LABELS[running[0].name] ? t(ANALYZER_LABELS[running[0].name]) : running[0].name })}
                </span>
              );
            }
            return (
              <span className="flex items-center gap-2 font-mono text-[11px] text-ink-200">
                <span className="w-1.5 h-1.5 rounded-full bg-signal-amber pulse-dot" />
                {submission.status_message ? t(submission.status_message) : t("Processing...")}
              </span>
            );
          })()}
        </div>
      )}

      {!isProcessing && doneCount === 0 && skippedCount === totalCount && totalCount > 0 && (
        <div className="mb-6 flex items-start gap-3 px-3 py-2.5 border-l-2 border-signal-blood/60 bg-signal-blood/5">
          <span className="mt-0.5 text-signal-blood text-[13px]">!</span>
          <span className="font-mono text-[11px] text-ink-300 leading-relaxed">
            {t("This check did not start. Upload the file again; if it happens again, let us know.")}
          </span>
        </div>
      )}

      {hasIncompleteResults && !(doneCount === 0 && skippedCount === totalCount) && (
        <div className="mb-6 flex items-start gap-3 px-3 py-2.5 border-l-2 border-signal-amber/60 bg-signal-amber/5">
          <span className="mt-0.5 text-signal-amber text-[13px]">⚠</span>
          <span className="font-mono text-[11px] text-ink-300 leading-relaxed">
            {t("Some analyzers did not complete ({skipped} skipped, {failed} failed). Final verdict may be inaccurate.", { skipped: skippedCount, failed: errorCount })}
          </span>
        </div>
      )}

      <div className="space-y-1">
        {steps.map((step, i) => (
          <AnalyzerRow key={step.name} step={step} isLast={i === steps.length - 1} index={i} done={!isProcessing} image={image} showRaw={showRaw} />
        ))}
      </div>
    </div>
  );
}
