import clsx from "clsx";
import { useState } from "react";
import type { Submission } from "../types";
import { msg, t } from "../i18n";
import { mapPending } from "../hooks/useUpload";

type Region = { bbox: number[]; kind: string; confidence: string; likely_ai?: boolean };
type MapEvidence = { status?: string; reason?: string; regions?: Region[]; map_url?: string; image_size?: number[] };

const REGION_TEXT: Record<string, string> = {
  copy_move: msg("This area repeats another part of the same photo: it may have been copied within the image."),
  jpeg_history: msg("This area was compressed differently from the rest of the photo. That happens when a piece is pasted from another image or redrawn."),
  inconsistent_high: msg("This area does not match the rest of the photo: it may have been pasted in or redrawn."),
  inconsistent_medium: msg("Possible mismatch, look at this area more closely."),
};

const QUIET_TEXT: Record<string, string> = {
  no_region_passed: msg("No signs of local editing were found. This does not prove the photo is genuine."),
  weak_signals: msg("We can't reliably show edited areas for this file (for example, because of strong compression)."),
  low_quality_jpeg: msg("We can't reliably show edited areas for this file (for example, because of strong compression)."),
  whole_image_ai: msg("The whole picture looks AI-generated, so we don't show a map of separate areas."),
  global_change: msg("The changes cover almost the whole photo (a global filter or a full redraw), so a map of areas would mislead."),
  too_small: msg("The image is too small for a map of edited areas."),
  too_large: msg("The photo is too large for a map of edited areas."),
};

function absolute(url: string): string {
  const apiBase = import.meta.env.VITE_API_URL?.replace("/api/v1", "") || "";
  return url.startsWith("http") ? url : `${apiBase}${url}`;
}

function regionText(r: Region): string {
  const key = r.kind === "inconsistent" ? `inconsistent_${r.confidence === "high" ? "high" : "medium"}` : r.kind;
  return t(REGION_TEXT[key] ?? REGION_TEXT.inconsistent_medium);
}

export function mapEvidence(submission: Submission): MapEvidence | null {
  const result = submission.analysis_results?.find((r) => r.analyzer_name === "manipulation_map" && r.verdict !== "error");
  return (result?.evidence as MapEvidence | undefined) ?? null;
}

export default function PhotoWithMap({ submission, student }: { submission: Submission; student: boolean }) {
  const [opacity, setOpacity] = useState(45);
  const ev = mapEvidence(submission);
  const size = ev?.image_size;
  const regions = ev?.status === "regions_found" && size?.length === 2 ? ev.regions ?? [] : [];
  const show = !student && regions.length > 0;
  const quiet = !student && !show && ev?.reason ? QUIET_TEXT[ev.reason] : undefined;
  const waiting = !student && !ev && mapPending(submission);

  if (!submission.file_url) return null;
  return (
    <div className="px-6 py-4 border-b border-ink-700">
      <div className="relative inline-block max-w-full align-top">
        <img
          src={submission.file_url}
          alt={submission.original_filename}
          className="block max-h-96 max-w-full border border-ink-700"
          loading="lazy"
          onError={(e) => {
            e.currentTarget.parentElement?.parentElement?.style.setProperty("display", "none");
          }}
        />
        {show && ev?.map_url && (
          <img
            src={absolute(ev.map_url)}
            alt=""
            aria-hidden="true"
            className="absolute inset-0 w-full h-full pointer-events-none"
            style={{ opacity: opacity / 100, mixBlendMode: "screen", filter: "sepia(1) saturate(6) hue-rotate(-15deg)" }}
          />
        )}
        {show && size &&
          regions.map((r, i) => (
            <div
              key={i}
              className={clsx("absolute border-2 border-signal-amber pointer-events-none", r.confidence !== "high" && "border-dashed")}
              style={{
                left: `${(r.bbox[0] / size[0]) * 100}%`,
                top: `${(r.bbox[1] / size[1]) * 100}%`,
                width: `${((r.bbox[2] - r.bbox[0]) / size[0]) * 100}%`,
                height: `${((r.bbox[3] - r.bbox[1]) / size[1]) * 100}%`,
              }}
            >
              <span className="absolute left-0 top-0 -translate-y-full bg-signal-amber text-ink-950 font-mono text-[10px] px-1">{i + 1}</span>
            </div>
          ))}
      </div>
      {show && (
        <div className="mt-3 max-w-2xl">
          <div className="flex items-center justify-between gap-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("Where the photo may have been changed")}</span>
            <label className="flex items-center gap-2 font-mono text-[9px] text-ink-500">
              {t("opacity")}
              <input type="range" min={0} max={100} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} className="w-20 accent-signal-amber" />
            </label>
          </div>
          <ol className="mt-2 space-y-1.5 text-sm text-ink-200 leading-relaxed">
            {regions.map((r, i) => (
              <li key={i}>
                <span className="font-mono text-signal-amber mr-1.5">{i + 1}.</span>
                {regionText(r)}
                {r.likely_ai && ` ${t("This area looks AI-generated.")}`}
              </li>
            ))}
          </ol>
          <p className="text-xs text-ink-500 mt-2">{t("The map shows inconsistencies, not proof of forgery.")}</p>
        </div>
      )}
      {quiet && <p className="text-xs text-ink-400 mt-2 max-w-2xl">{t(quiet)}</p>}
      {waiting && <p className="text-xs text-ink-400 mt-2 max-w-2xl">{t("The map of edited areas is still being drawn; it will appear here in a minute or two.")}</p>}
    </div>
  );
}
