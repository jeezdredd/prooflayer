import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import type { Submission } from "../types";
import AnalyzerTimeline from "./AnalyzerTimeline";
import TextReport from "./TextReport";
import OriginalityPanel from "./OriginalityPanel";
import AiTracePanel from "./AiTracePanel";
import MediaSummary, { hasProvenanceProof } from "./MediaSummary";
import PhotoWithMap from "./PhotoWithMap";
import TeacherSummary, { isTextSubmission } from "./TeacherSummary";
import { isClassView, isStudentView, longDate } from "./resultView";
import { VERDICT_DISCLAIMER } from "../legal";
import { useAuthStore } from "../stores/authStore";
import { locale, msg, t } from "../i18n";

const CHARS = "abcdefghijklmnopqrstuvwxyz0123456789";

function DecryptText({ text }: { text: string }) {
  const [display, setDisplay] = useState(text);
  const iterRef = useRef(0);

  useEffect(() => {
    iterRef.current = 0;
    const interval = setInterval(() => {
      iterRef.current += 2;
      setDisplay(
        text
          .split("")
          .map((char, i) => {
            if (char === " " || char === "." || char === "_" || char === "-" || char === "/") return char;
            if (i < iterRef.current) return char;
            return CHARS[Math.floor(Math.random() * CHARS.length)];
          })
          .join("")
      );
      if (iterRef.current >= text.length) clearInterval(interval);
    }, 40);
    return () => clearInterval(interval);
  }, [text]);

  return <span>{display}</span>;
}

const BAR_COUNT = 32;
const IDLE_HEIGHTS = Array.from({ length: BAR_COUNT }, (_, i) => Math.sin(i * 0.4) * 15 + 20);

function AudioVisualizer({ src }: { src: string }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [barHeights, setBarHeights] = useState(IDLE_HEIGHTS);
  const ctxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const rafRef = useRef<number>(0);

  const startVisualizer = () => {
    if (!audioRef.current) return;
    if (!ctxRef.current) {
      const ctx = new AudioContext();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 128;
      const source = ctx.createMediaElementSource(audioRef.current);
      source.connect(analyser);
      analyser.connect(ctx.destination);
      ctxRef.current = ctx;
      analyserRef.current = analyser;
      sourceRef.current = source;
    }
    const analyser = analyserRef.current!;
    const data = new Uint8Array(analyser.frequencyBinCount);
    const draw = () => {
      analyser.getByteFrequencyData(data);
      const step = Math.floor(data.length / BAR_COUNT);
      setBarHeights(
        Array.from({ length: BAR_COUNT }, (_, i) => {
          const val = data[i * step] ?? 0;
          return Math.max(8, (val / 255) * 100);
        })
      );
      rafRef.current = requestAnimationFrame(draw);
    };
    draw();
  };

  const stopVisualizer = () => {
    cancelAnimationFrame(rafRef.current);
    setBarHeights(IDLE_HEIGHTS);
  };

  const toggle = () => {
    if (!audioRef.current) return;
    if (playing) {
      audioRef.current.pause();
      stopVisualizer();
    } else {
      audioRef.current.play();
      startVisualizer();
    }
    setPlaying((p) => !p);
  };

  useEffect(() => () => { cancelAnimationFrame(rafRef.current); ctxRef.current?.close(); }, []);

  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

  return (
    <div className="space-y-3">
      <audio
        ref={audioRef}
        src={src}
        onTimeUpdate={() => {
          if (!audioRef.current) return;
          setProgress((audioRef.current.currentTime / (audioRef.current.duration || 1)) * 100);
        }}
        onLoadedMetadata={() => setDuration(audioRef.current?.duration || 0)}
        onEnded={() => { setPlaying(false); stopVisualizer(); }}
      />

      <div className="flex items-end gap-px h-12">
        {barHeights.map((h, i) => (
          <div
            key={i}
            className={clsx("flex-1 rounded-sm", playing ? "bg-signal-amber" : "bg-ink-700")}
            style={{ height: `${h}%`, transition: playing ? "height 80ms ease-out" : "height 300ms ease-out, background-color 300ms" }}
          />
        ))}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={toggle}
          className="w-8 h-8 border border-ink-600 hover:border-signal-amber flex items-center justify-center text-ink-300 hover:text-signal-amber transition shrink-0"
        >
          {playing ? (
            <span className="flex gap-0.5">
              <span className="w-1 h-3 bg-current" />
              <span className="w-1 h-3 bg-current" />
            </span>
          ) : (
            <span className="w-0 h-0 border-t-4 border-b-4 border-l-8 border-transparent border-l-current ml-0.5" />
          )}
        </button>
        <div
          className="flex-1 relative h-1 bg-ink-800 cursor-pointer"
          onClick={(e) => {
            if (!audioRef.current) return;
            const rect = e.currentTarget.getBoundingClientRect();
            audioRef.current.currentTime = ((e.clientX - rect.left) / rect.width) * (audioRef.current.duration || 0);
          }}
        >
          <div className="absolute inset-y-0 left-0 bg-signal-amber transition-none" style={{ width: `${progress}%` }} />
        </div>
        <span className="font-mono text-[10px] text-ink-500 tabular-nums shrink-0">{fmt(duration)}</span>
      </div>
    </div>
  );
}

interface ResultCardProps {
  submission: Submission;
  runningAnalyzers?: Set<string>;
}

const VERDICT_TONE: Record<string, { color: string; label: string; ring: string; sub?: string }> = {
  authentic: { color: "text-signal-sage", ring: "border-signal-sage/40", label: msg("REAL") },
  authentic_edited: { color: "text-signal-amber", ring: "border-signal-amber/40", label: msg("REAL · EDITED"), sub: msg("Image appears genuine but shows signs of digital editing or compositing.") },
  suspicious: { color: "text-signal-amber", ring: "border-signal-amber/40", label: msg("Suspicious") },
  likely_fake: { color: "text-signal-blood", ring: "border-signal-blood/40", label: msg("Likely AI") },
  fake: { color: "text-signal-blood", ring: "border-signal-blood/60", label: msg("AI") },
  needs_review: { color: "text-signal-violet", ring: "border-signal-violet/40", label: msg("Needs Review") },
  inconclusive: { color: "text-ink-300", ring: "border-ink-600", label: msg("Inconclusive") },
};

const BAR_ZONES = [
  { from: 0, to: 35, tone: "bg-signal-sage/15" },
  { from: 35, to: 50, tone: "bg-signal-amber/15" },
  { from: 50, to: 60, tone: "bg-ink-700/60" },
  { from: 60, to: 75, tone: "bg-signal-blood/10" },
  { from: 75, to: 100, tone: "bg-signal-blood/20" },
];

const NO_BAR_VERDICTS = ["needs_review", "inconclusive", ""];

function shortHash(hash: string | undefined) {
  if (!hash) return "-";
  return `${hash.slice(0, 8)}…${hash.slice(-6)}`;
}

function formatSize(bytes: number) {
  const number = (n: number) => n.toLocaleString(locale(), { maximumFractionDigits: 1 });
  if (bytes < 1024) return t("{n} B", { n: bytes });
  if (bytes < 1024 * 1024) return t("{n} KB", { n: number(bytes / 1024) });
  return t("{n} MB", { n: number(bytes / 1024 / 1024) });
}

function kindText(mime: string | undefined) {
  const value = mime ?? "";
  if (value.startsWith("image/")) return t("picture {format}", { format: value.split("/")[1].toUpperCase() });
  if (value.startsWith("video/")) return t("video");
  if (value.startsWith("audio/")) return t("audio");
  if (value === "application/pdf") return t("PDF document");
  if (value.includes("wordprocessingml")) return t("Word document");
  if (value === "text/plain") return t("text");
  return value || t("unknown");
}

function VersionNote({ submission }: { submission: Submission }) {
  const ensemble = submission.ensemble;
  if (!ensemble || ensemble.is_current) return null;
  const text =
    ensemble.version === ensemble.current_version
      ? t("This work was checked before the last update of Tribunal. Press \"Re-analyze\" and the old result will be replaced with the new one.")
      : t("This work was checked by an earlier version of Tribunal ({version}). Version {current} is out: press \"Re-analyze\" and the old result will be replaced with the new one.", {
          version: ensemble.version,
          current: ensemble.current_version,
        });
  return <p className="text-xs text-signal-amber/90 leading-snug mt-2 max-w-md">{text}</p>;
}

function ClassHeader({ submission, student, isProcessing }: { submission: Submission; student: boolean; isProcessing: boolean }) {
  const title = student ? t("Your work") : submission.student_name || submission.original_filename;
  const facts = [
    submission.classroom_name,
    t("handed in {date}", { date: longDate(submission.created_at) }),
    `${kindText(submission.mime_type)}, ${formatSize(submission.file_size)}`,
  ].filter(Boolean);

  return (
    <header className="flex flex-wrap items-start justify-between gap-4 border-b border-ink-700 px-4 sm:px-6 py-4 sm:py-5">
      <div className="min-w-0">
        <h2 className="font-display text-2xl sm:text-3xl text-ink-50 leading-tight break-words">{title}</h2>
        <p className="mt-2 text-sm text-ink-300">{facts.join(" · ")}</p>
        {title !== submission.original_filename && (
          <p className="mt-1 text-xs text-ink-500 break-all">{submission.original_filename}</p>
        )}
        {!student && !isProcessing && <VersionNote submission={submission} />}
      </div>
      {isProcessing && (
        <div className="text-right">
          <div className="font-display text-2xl text-signal-amber italic">{t("analyzing…")}</div>
          <div className="text-xs text-ink-500 mt-1">{t("The result appears here when every check is done.")}</div>
        </div>
      )}
    </header>
  );
}

function MainHeader({ submission, isProcessing, proof }: { submission: Submission; isProcessing: boolean; proof: boolean }) {
  const verdict = VERDICT_TONE[submission.final_verdict] || VERDICT_TONE.inconclusive;
  return (
    <header className="flex items-stretch border-b border-ink-700">
      <div className="flex-1 px-4 sm:px-6 py-4 sm:py-5 min-w-0">
        <div className="flex items-center gap-3 mb-3">
          <span className="label-mono">{t("Evidence File")}</span>
          <span className="font-mono text-[10px] text-ink-500">/</span>
          <span className="font-mono text-[10px] text-ink-400 ticker">
            {submission.id.slice(0, 8).toUpperCase()}
          </span>
        </div>
        <h2 className="font-display text-2xl sm:text-3xl text-ink-50 leading-tight break-all">
          <DecryptText text={submission.original_filename} />
        </h2>
        <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 font-mono text-[11px] text-ink-400">
          <span><span className="text-ink-600">{t("type:")}</span> {submission.mime_type || t("unknown")}</span>
          <span><span className="text-ink-600">{t("size:")}</span> {formatSize(submission.file_size)}</span>
          <span><span className="text-ink-600">sha256:</span> <span className="ticker">{shortHash(submission.sha256_hash)}</span></span>
        </div>
        {!isProcessing && <VersionNote submission={submission} />}
      </div>

      <div className="reg-tick" />

      <div className="px-4 sm:px-6 py-4 sm:py-5 flex flex-col items-end justify-between min-w-[110px] sm:min-w-[180px]">
        {!isProcessing && (
          <span className={clsx("badge", verdict.color, verdict.ring)}>
            <span className="w-1 h-1 bg-current rounded-full" />
            {t(verdict.label)}
          </span>
        )}
        {!isProcessing && proof && (
          <div className="text-sm text-signal-blood mt-2 text-right max-w-[220px] leading-snug">{t("Made by AI: the invisible mark in the file proves it.")}</div>
        )}
        {!isProcessing && submission.ensemble && (
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-600 mt-2 text-right">
            {t("verdict by {name}", { name: submission.ensemble.label })}
          </div>
        )}
        {!isProcessing && (
          <div className="text-[11px] leading-snug text-ink-500 mt-2 text-right max-w-[220px]">
            {proof ? t("The mark is put there by the AI generator itself, so this is not a guess.") : t(VERDICT_DISCLAIMER)}
          </div>
        )}
        {isProcessing && (
          <div className="text-right mt-2">
            <div className="font-display text-2xl text-signal-amber italic">{t("analyzing…")}</div>
            <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mt-1">
              {t("Awaiting verdict")}
            </div>
          </div>
        )}
      </div>
    </header>
  );
}

function ScoreBar({ score }: { score: number }) {
  return (
    <div className="px-6 py-3 border-b border-ink-700">
      <div className="flex justify-between mb-1.5 text-[11px] text-ink-400">
        <span>{t("Looks human-made")}</span>
        <span>{t("Looks AI-made")}</span>
      </div>
      <div className="relative h-2 bg-ink-800">
        {BAR_ZONES.map((zone) => (
          <div key={zone.from} className={clsx("absolute inset-y-0", zone.tone)} style={{ left: `${zone.from}%`, width: `${zone.to - zone.from}%` }} />
        ))}
        <div
          className="absolute -top-1 -bottom-1 w-0.5 bg-ink-50 shadow-[0_0_12px_rgba(255,255,255,0.6)]"
          style={{ left: `${score * 100}%`, transform: "translateX(-1px)" }}
        />
      </div>
      <p className="mt-1.5 text-[11px] text-ink-500">
        {t("The marker shows where the detectors' combined score falls. Green: like a camera or a person, yellow and grey: unclear, red: like AI.")}
      </p>
    </div>
  );
}

function PipelineDetails({ submission, runningAnalyzers, showRaw }: { submission: Submission; runningAnalyzers?: Set<string>; showRaw: boolean }) {
  return (
    <details className="px-6 py-4 group">
      <summary className="cursor-pointer list-none font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 hover:text-ink-200">
        <span className="group-open:hidden">+ {t("Technical details")}</span>
        <span className="hidden group-open:inline">- {t("Technical details")}</span>
      </summary>
      <div className="pt-4">
        <AnalyzerTimeline submission={submission} runningAnalyzers={runningAnalyzers} showRaw={showRaw} />
      </div>
    </details>
  );
}

export default function ResultCard({ submission, runningAnalyzers }: ResultCardProps) {
  const verdict = VERDICT_TONE[submission.final_verdict] || VERDICT_TONE.inconclusive;
  const score = submission.final_score;
  const isProcessing = submission.status === "processing" || submission.status === "pending";
  const studentOnly = !!useAuthStore((s) => s.user?.student_only);
  const isStaff = !!useAuthStore((s) => s.user?.is_staff);
  const student = submission.viewer_role ? isStudentView(submission) : studentOnly;
  const classView = isClassView(submission);
  const text = isTextSubmission(submission);
  const proof = hasProvenanceProof(submission);
  const shared = { submission, student };
  const showBar = !classView && !proof && score !== null && score !== undefined && !NO_BAR_VERDICTS.includes(submission.final_verdict);
  const showPipeline = isProcessing || (!student && (isStaff || !(classView && text)));

  return (
    <article className="case-card crop-marks animate-rise">
      {classView ? (
        <ClassHeader submission={submission} student={student} isProcessing={isProcessing} />
      ) : (
        <MainHeader submission={submission} isProcessing={isProcessing} proof={proof} />
      )}

      {text ? <TeacherSummary submission={submission} student={student} /> : classView && <MediaSummary submission={submission} student={student} />}

      {!classView && verdict.sub && (
        <div className="px-6 py-2.5 border-b border-ink-700 bg-signal-amber/5 flex items-center gap-2.5">
          <span className="w-1 h-1 rounded-full bg-signal-amber shrink-0" />
          <span className="font-mono text-[11px] text-signal-amber">{t(verdict.sub)}</span>
        </div>
      )}

      {showBar && <ScoreBar score={score} />}

      {submission.is_known_fake && (
        <div className="px-6 py-3 border-b border-ink-700 bg-signal-blood/5 flex items-center gap-3">
          <span className="w-6 h-6 border border-signal-blood text-signal-blood text-xs flex items-center justify-center font-bold">!</span>
          <div className="flex-1">
            <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-signal-blood">
              {classView ? t("Known AI-made file") : t("Known fake match")}
            </div>
            <div className="text-sm text-ink-200">
              {classView ? t("This exact file is already on our list of confirmed AI-made files.") : t("This exact file is already in our list of confirmed fakes.")}
            </div>
          </div>
        </div>
      )}

      <AiTracePanel submission={submission} />

      {submission.file_url && submission.mime_type?.startsWith("image/") && <PhotoWithMap submission={submission} student={student} />}

      {submission.file_url && submission.mime_type?.startsWith("audio/") && (
        <div className="px-6 py-4 border-b border-ink-700">
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-3">{t("Audio File")}</div>
          <AudioVisualizer src={submission.file_url} />
        </div>
      )}

      {submission.file_url && submission.mime_type?.startsWith("video/") && (
        <div className="px-6 py-4 border-b border-ink-700">
          <video controls preload="metadata" src={submission.file_url} className="max-h-72 max-w-full border border-ink-700" />
        </div>
      )}

      <OriginalityPanel {...shared} />
      <TextReport {...shared} />

      {showPipeline &&
        (isProcessing ? (
          <div className="px-6 py-6">
            <AnalyzerTimeline submission={submission} runningAnalyzers={runningAnalyzers} showRaw={isStaff} />
          </div>
        ) : (
          <PipelineDetails submission={submission} runningAnalyzers={runningAnalyzers} showRaw={isStaff} />
        ))}
    </article>
  );
}
