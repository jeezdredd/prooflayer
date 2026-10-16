import clsx from "clsx";
import { useEffect, useState } from "react";
import { msg, t } from "../i18n";
import TaskSteps from "./TaskSteps";
import type { Step } from "./AnalyzerTimeline";

interface UploadProgressProps {
  progress: number;
  status: "uploading" | "processing";
  statusMessage?: string;
  filename?: string;
  fileSize?: number;
  previewUrl?: string;
  previewKind?: "image" | "video";
  steps?: Step[];
}

const STAGES = [
  { key: "uploading", label: msg("Transmit"), code: "01" },
  { key: "queued", label: msg("Queue"), code: "02" },
  { key: "analyzing", label: msg("Analyze"), code: "03" },
] as const;

const TIPS = [
  msg("Computing SHA-256 fingerprint…"),
  msg("Generating perceptual hash for similarity search…"),
  msg("Reading EXIF metadata and editor signatures…"),
  msg("Re-saving JPEG slice for ELA delta…"),
  msg("Loading image classifiers (ensemble vote)…"),
  msg("Pre-checking content type (photo vs diagram)…"),
  msg("Cold-loading vision model (first run is slow)…"),
  msg("Examining lighting, texture, fingers, eyes…"),
  msg("Aggregating weighted confidence…"),
  msg("Cross-referencing community fakes index…"),
];

export default function UploadProgress({
  progress,
  status,
  statusMessage,
  filename,
  fileSize,
  previewUrl,
  previewKind,
  steps,
}: UploadProgressProps) {
  const isUploading = status === "uploading";
  const currentStage = isUploading
    ? "uploading"
    : statusMessage?.toLowerCase().includes("queue")
    ? "queued"
    : "analyzing";
  const currentIdx = STAGES.findIndex((s) => s.key === currentStage);

  const [tipIdx, setTipIdx] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (isUploading) return;
    const start = Date.now();
    const tip = setInterval(() => setTipIdx((i) => (i + 1) % TIPS.length), 3200);
    const clk = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 250);
    return () => {
      clearInterval(tip);
      clearInterval(clk);
    };
  }, [isUploading]);

  return (
    <div className="case-card crop-marks mt-6 animate-rise">
      <div className="flex items-center justify-between px-6 py-3 border-b border-ink-700">
        <div className="flex items-center gap-3">
          <span className="w-1.5 h-1.5 rounded-full bg-signal-cyan animate-pulse" />
          <span className="label-mono">{t("Transmission")}</span>
        </div>
        <span className="font-mono text-[10px] text-ink-500 ticker">
          {isUploading ? t("OUTBOUND") : t("PROCESSING · {n}s", { n: elapsed })}
        </span>
      </div>

      <div className="px-6 py-5">
        {filename && (
          <div className="flex items-center gap-3 pb-4 mb-4 border-b border-dashed border-ink-700">
            <div className="w-10 h-10 rounded-lg bg-ink-800 flex items-center justify-center text-ink-300 font-mono text-[10px]">
              {filename.split(".").pop()?.toUpperCase().slice(0, 4) || t("FILE")}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-mono text-xs text-ink-100 truncate">{filename}</div>
              {fileSize !== undefined && (
                <div className="font-mono text-[10px] text-ink-500 mt-0.5 ticker">
                  {formatSize(fileSize)} {isUploading && `· ${progress}%`}
                </div>
              )}
            </div>
          </div>
        )}

        {previewUrl && previewKind && (
          <div className="mb-5 flex justify-center overflow-hidden rounded-lg bg-ink-900/60">
            <div className="relative overflow-hidden">
              {previewKind === "image" ? (
                <img src={previewUrl} alt="" className={clsx("block max-w-full max-h-72 transition-opacity duration-700", isUploading ? "opacity-50" : "opacity-90")} />
              ) : (
                <video src={previewUrl} muted playsInline preload="metadata" className={clsx("block max-w-full max-h-72 transition-opacity duration-700", isUploading ? "opacity-50" : "opacity-90")} />
              )}
              {!isUploading && (
                <>
                  <div className="scan-grid absolute inset-0 pointer-events-none" />
                  <div className="scan-line absolute inset-x-0 pointer-events-none" />
                  <span className="absolute top-2 left-2 w-4 h-4 border-t-2 border-l-2 border-signal-cyan/80 rounded-none" />
                  <span className="absolute top-2 right-2 w-4 h-4 border-t-2 border-r-2 border-signal-cyan/80 rounded-none" />
                  <span className="absolute bottom-2 left-2 w-4 h-4 border-b-2 border-l-2 border-signal-cyan/80 rounded-none" />
                  <span className="absolute bottom-2 right-2 w-4 h-4 border-b-2 border-r-2 border-signal-cyan/80 rounded-none" />
                  <span className="absolute bottom-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-ink-950/80 border border-signal-cyan/40 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-signal-cyan backdrop-blur-sm">
                    {previewKind === "image" ? t("Analyzing image") : t("Analyzing video")}
                  </span>
                </>
              )}
            </div>
          </div>
        )}

        {/* Stage tracker */}
        <div className="flex items-center gap-2 mb-4">
          {STAGES.map((stage, i) => {
            const done = i < currentIdx;
            const active = i === currentIdx;
            return (
              <div key={stage.key} className="flex-1 flex items-center gap-2 min-w-0">
                <div
                  className={clsx(
                    "w-7 h-7 border flex items-center justify-center font-mono text-[10px] shrink-0 transition-all",
                    done && "border-signal-sage text-signal-sage bg-signal-sage/10",
                    active && "border-signal-amber text-signal-amber bg-signal-amber/10",
                    !done && !active && "border-ink-700 text-ink-500 bg-ink-850",
                  )}
                >
                  {done ? "✓" : stage.code}
                </div>
                <span
                  className={clsx(
                    "font-mono text-[10px] uppercase tracking-[0.14em] whitespace-nowrap",
                    done && "text-signal-sage",
                    active && "text-signal-amber",
                    !done && !active && "text-ink-500",
                  )}
                >
                  {t(stage.label)}
                </span>
                {i < STAGES.length - 1 && (
                  <div
                    className={clsx(
                      "flex-1 h-px transition-colors min-w-[12px]",
                      i < currentIdx ? "bg-signal-sage/50" : "bg-ink-700",
                    )}
                  />
                )}
              </div>
            );
          })}
        </div>

        {/* Progress bar */}
        <div className="relative h-1 bg-ink-800 overflow-hidden">
          <div
            className={clsx(
              "absolute inset-y-0 left-0 transition-all duration-500 ease-out",
              isUploading ? "bg-signal-cyan" : "bg-signal-amber",
            )}
            style={{ width: isUploading ? `${progress}%` : "100%" }}
          />
          {!isUploading && (
            <div className="absolute inset-y-0 h-full w-1/4 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-scan-bar" />
          )}
        </div>

        <div className="mt-2 flex items-center justify-between font-mono text-[10px]">
          <span className={clsx("uppercase tracking-[0.14em] ticker", isUploading ? "text-signal-cyan" : "shimmer-text text-signal-amber")}>
            {isUploading ? t("TRANSMITTING · {n}%", { n: progress }) : statusMessage ? t(statusMessage) : t("PROCESSING…")}
          </span>
          {!isUploading && (
            <span className="text-ink-500 uppercase tracking-[0.14em] ticker">
              T+{String(elapsed).padStart(3, "0")}s
            </span>
          )}
        </div>

        {/* Live tip log */}
        {!isUploading && steps && steps.length > 0 && <TaskSteps steps={steps} />}

        {!isUploading && !(steps && steps.length > 0) && (
          <div className="mt-4 border-l-2 border-signal-amber/40 pl-3 py-2 bg-signal-amber/[0.04]">
            <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500 mb-1">{t("Worker log")}</div>
            <div key={tipIdx} className="font-mono text-[11px] text-ink-200 leading-relaxed animate-fade-in-up">
              <span className="text-signal-amber mr-1.5">›</span>
              {t(TIPS[tipIdx])}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}
