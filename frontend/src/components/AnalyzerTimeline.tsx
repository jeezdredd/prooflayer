import clsx from "clsx";
import { useState } from "react";
import type { AnalysisResult, ExpectedAnalyzer, Submission } from "../types";

const VERDICT_COLOR: Record<string, string> = {
  authentic: "text-green-700 bg-green-100 border-green-200",
  suspicious: "text-yellow-700 bg-yellow-100 border-yellow-200",
  fake: "text-red-700 bg-red-100 border-red-200",
  inconclusive: "text-gray-600 bg-gray-100 border-gray-200",
  error: "text-gray-500 bg-gray-100 border-gray-200",
};

const ANALYZER_LABELS: Record<string, string> = {
  metadata: "Metadata & EXIF",
  ela: "Error Level Analysis",
  ai_detector: "AI Image Detector",
  llm_vision: "Vision LLM",
  video_frame: "Video Frame Analysis",
  audio_spectrogram: "Audio Spectrogram",
  llm_text: "Text LLM",
};

interface Step {
  name: string;
  description: string;
  result?: AnalysisResult;
  state: "done" | "running" | "pending" | "skipped";
}

function buildSteps(submission: Submission): Step[] {
  const expected: ExpectedAnalyzer[] = submission.expected_analyzers || [];
  const isProcessing = submission.status === "processing" || submission.status === "pending";
  const isFailed = submission.status === "failed";

  const sources: Step[] = expected.map((a) => {
    const result = submission.analysis_results.find((r) => r.analyzer_name === a.name);
    let state: Step["state"];
    if (result) state = "done";
    else if (isProcessing) state = "pending";
    else if (isFailed) state = "skipped";
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

  if (isProcessing) {
    const firstPendingIdx = sources.findIndex((s) => s.state === "pending");
    if (firstPendingIdx >= 0) sources[firstPendingIdx].state = "running";
  }

  return sources;
}

function StepRow({ step, isLast }: { step: Step; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const label = ANALYZER_LABELS[step.name] || step.name;
  const verdict = step.result?.verdict || "";
  const verdictClass = VERDICT_COLOR[verdict] || VERDICT_COLOR.inconclusive;

  return (
    <div className="relative pl-10 pb-5 animate-fade-in-up">
      {!isLast && (
        <div className="absolute left-[15px] top-7 bottom-0 w-px bg-gray-200" />
      )}
      <div className="absolute left-0 top-0">
        <StepIcon state={step.state} verdict={verdict} />
      </div>

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left"
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="font-medium text-gray-900">{label}</div>
            {step.state === "running" && (
              <div className="text-xs text-blue-600 mt-0.5">Running...</div>
            )}
            {step.state === "pending" && (
              <div className="text-xs text-gray-400 mt-0.5">Queued</div>
            )}
            {step.state === "skipped" && (
              <div className="text-xs text-gray-400 mt-0.5">Skipped</div>
            )}
            {step.result && step.result.execution_time != null && (
              <div className="text-xs text-gray-400 mt-0.5">
                {step.result.execution_time.toFixed(1)}s
              </div>
            )}
          </div>
          {step.result && (
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-sm text-gray-500 tabular-nums">
                {(step.result.confidence * 100).toFixed(0)}%
              </span>
              <span className={clsx("text-xs px-2 py-0.5 rounded-full border font-medium uppercase", verdictClass)}>
                {verdict || "—"}
              </span>
            </div>
          )}
        </div>

        {step.state === "running" && (
          <div className="mt-2 w-full h-1 bg-gray-100 rounded overflow-hidden">
            <div className="h-full w-1/3 bg-gradient-to-r from-transparent via-blue-500 to-transparent animate-scan-bar" />
          </div>
        )}
      </button>

      {expanded && (
        <div className="mt-2 text-xs text-gray-600 space-y-1 animate-fade-in-up">
          {step.description && <p>{step.description}</p>}
          {step.result?.error_message && (
            <p className="text-red-600">Error: {step.result.error_message}</p>
          )}
          {step.result && Object.keys(step.result.evidence || {}).length > 0 && (
            <pre className="text-[10px] bg-gray-50 border border-gray-200 rounded p-2 overflow-x-auto">
              {JSON.stringify(step.result.evidence, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function StepIcon({ state, verdict }: { state: Step["state"]; verdict: string }) {
  if (state === "done") {
    const cls =
      verdict === "fake" || verdict === "suspicious"
        ? "bg-red-500"
        : verdict === "authentic"
        ? "bg-green-500"
        : "bg-gray-400";
    return (
      <div className={clsx("w-[30px] h-[30px] rounded-full flex items-center justify-center text-white text-sm font-bold", cls)}>
        {verdict === "authentic" ? "✓" : verdict === "fake" || verdict === "suspicious" ? "!" : "·"}
      </div>
    );
  }
  if (state === "running") {
    return (
      <div className="w-[30px] h-[30px] rounded-full bg-blue-500 flex items-center justify-center animate-pulse-soft">
        <div className="w-3 h-3 rounded-full bg-white" />
      </div>
    );
  }
  if (state === "skipped") {
    return (
      <div className="w-[30px] h-[30px] rounded-full border-2 border-gray-200 bg-gray-50 flex items-center justify-center text-gray-400 text-sm">
        ×
      </div>
    );
  }
  return (
    <div className="w-[30px] h-[30px] rounded-full border-2 border-gray-200 bg-white flex items-center justify-center">
      <div className="w-2 h-2 rounded-full bg-gray-300" />
    </div>
  );
}

export default function AnalyzerTimeline({ submission }: { submission: Submission }) {
  const steps = buildSteps(submission);
  if (steps.length === 0) return null;

  const doneCount = steps.filter((s) => s.state === "done").length;
  const totalCount = steps.length;
  const isProcessing = submission.status === "processing" || submission.status === "pending";

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-sm font-semibold text-gray-700">Analyzer Pipeline</h4>
        <span className="text-xs text-gray-500 tabular-nums">
          {doneCount} / {totalCount} {isProcessing ? "running" : "complete"}
        </span>
      </div>
      {isProcessing && submission.status_message && (
        <div className="mb-4 px-3 py-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-800 animate-pulse-soft">
          {submission.status_message}
        </div>
      )}
      <div>
        {steps.map((step, i) => (
          <StepRow key={step.name} step={step} isLast={i === steps.length - 1} />
        ))}
      </div>
    </div>
  );
}
