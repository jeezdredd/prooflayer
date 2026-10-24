import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { ClassObjection, ClassSubmission } from "../types";
import { locale, msg, t, tn } from "../i18n";
import { VERDICT_DISCLAIMER } from "../legal";
import { STATUS_TEXT, plainOutcome, type CheckStatus } from "../components/TeacherSummary";

export type Viewer = "teacher" | "student";

export const FLAG_TEXT: Record<string, string> = {
  ai_text: msg("chatbot text"),
  ai_trace: msg("AI generator trace"),
  trace_hidden: msg("AI trace damaged"),
  ai_image: msg("looks AI-generated"),
  ai_media: msg("looks like generated sound or video"),
  hidden_text: msg("hidden text in file"),
  tricks: msg("disguised letters"),
  shadow: msg("follows an AI answer"),
  copy: msg("matches {n}%"),
  sources: msg("invented sources"),
  age: msg("vocabulary above age"),
  style: msg("unlike own earlier work"),
};
const STRONG_FLAGS = new Set(["ai_text", "ai_trace", "trace_hidden", "ai_image", "ai_media", "hidden_text", "tricks", "shadow", "sources"]);

const KIND_TEXT: Record<string, string> = {
  image: msg("picture"),
  audio: msg("audio"),
  video: msg("video"),
};

const PROGRESS_TEXT: Record<string, string> = {
  pending: msg("waiting for the check"),
  processing: msg("being checked"),
  failed: msg("check failed"),
};

function shortDate(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString(locale()) : "";
}

export function flagChip(flag: string, originality: number | null) {
  const text = flag === "copy" ? t(FLAG_TEXT.copy, { n: 100 - Math.round(originality ?? 100) }) : t(FLAG_TEXT[flag] ?? flag);
  const tone = STRONG_FLAGS.has(flag) ? "border-signal-blood/50 text-signal-blood" : "border-signal-amber/50 text-signal-amber";
  return <span key={flag} className={`inline-block border px-1.5 py-0.5 text-[10px] leading-tight ${tone}`}>{text}</span>;
}

export function rowOutcome(s: ClassSubmission, viewer: Viewer): { text: string; status: CheckStatus } {
  const student = viewer === "student";
  if (s.cleared) {
    return { text: student ? t("Your teacher accepted your objection") : t("Teacher cleared the work after the objection"), status: "ok" };
  }
  const base = plainOutcome(s.final_verdict, s.originality, s.note, student);
  if (s.flags.length > 0 && (base.status === "ok" || base.status === "wait")) {
    return { text: student ? t("Your teacher may ask you about this work") : t("Worth a look: see what the checks found"), status: "look" };
  }
  return { text: t(base.text), status: base.status };
}

export function objectionLine(o: ClassObjection, viewer: Viewer): { text: string; tone: string } {
  if (o.status === "open") {
    if (viewer === "student") {
      return o.overdue
        ? { text: t("Objection sent, the teacher has not answered yet"), tone: "text-signal-amber" }
        : { text: t("Objection sent, the teacher answers by {date}", { date: shortDate(o.due_at) }), tone: "text-signal-amber" };
    }
    return o.overdue
      ? { text: t("Objection overdue: the answer was due by {date}", { date: shortDate(o.due_at) }), tone: "text-signal-blood" }
      : { text: t("Objection waiting for an answer by {date}", { date: shortDate(o.due_at) }), tone: "text-signal-amber" };
  }
  const date = shortDate(o.responded_at);
  return o.decision === "changed"
    ? { text: t("Objection answered {date}: suspicion cleared", { date }), tone: "text-signal-sage" }
    : { text: t("Objection answered {date}: verdict upheld", { date }), tone: "text-ink-400" };
}

function sizeText(s: ClassSubmission): string {
  if (s.words != null) return tn(s.words, "{n} word", "{n} words");
  const kind = s.mime_type.split("/")[0];
  return t(KIND_TEXT[kind] ?? msg("document"));
}

export default function SubmissionRows({ rows, viewer, empty }: { rows: ClassSubmission[]; viewer: Viewer; empty?: ReactNode }) {
  if (rows.length === 0) return <div className="py-4 text-sm text-ink-500">{empty ?? t("Nothing submitted yet.")}</div>;
  const teacher = viewer === "teacher";
  return (
    <div>
      <p className="text-[11px] text-ink-600 mb-2">{t(VERDICT_DISCLAIMER)}</p>
      <div className="divide-y divide-[var(--line-strong)]">
        <div className="hidden md:grid md:grid-cols-12 gap-3 pb-1 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-600">
          {teacher && <span className="md:col-span-2">{t("Student")}</span>}
          <span className={teacher ? "md:col-span-5" : "md:col-span-7"}>{teacher ? t("Work and what the checks found") : t("Work")}</span>
          <span className="md:col-span-2">{t("Length")}</span>
          <span className="md:col-span-3">{t("Result")}</span>
        </div>
        {rows.map((s) => {
          const done = s.status === "completed";
          const outcome = done ? rowOutcome(s, viewer) : null;
          const objection = s.objection ? objectionLine(s.objection, viewer) : null;
          return (
            <Link key={s.id} to={`/results/${s.id}`} state={{ supervising: teacher }}
              className="grid grid-cols-[1fr_auto] md:grid-cols-12 gap-3 items-center py-3 hover:bg-ink-800/40 px-2 -mx-2 transition-colors">
              {teacher && (
                <span className="md:col-span-2 text-ink-300 truncate">
                  {s.unattributed ? <span className="text-ink-500">{t("No student (teacher check)")}</span> : s.student}
                  {s.uploaded_by && <span className="block font-mono text-[10px] text-ink-600 truncate">{t("uploaded by {name}", { name: s.uploaded_by })}</span>}
                </span>
              )}
              <span className={`${teacher ? "md:col-span-5" : "md:col-span-7"} min-w-0`}>
                <span className="block text-ink-50 truncate">{s.original_filename}</span>
                {done && !s.cleared && (
                  <span className="flex flex-wrap gap-1 mt-1">
                    {s.flags.length > 0
                      ? s.flags.map((f) => flagChip(f, s.originality))
                      : outcome?.status === "ok" && <span className="text-[10px] text-signal-sage">{t("no check raised a concern")}</span>}
                  </span>
                )}
                {objection && <span className={`block text-[11px] mt-1 ${objection.tone}`}>{objection.text}</span>}
              </span>
              <span className="md:col-span-2 font-mono text-[11px] text-ink-500 hidden md:block">{sizeText(s)}</span>
              <span className="md:col-span-3">
                {outcome
                  ? <span className={`text-sm leading-snug ${STATUS_TEXT[outcome.status]}`}>{outcome.text}</span>
                  : <span className="text-sm text-ink-400">{t(PROGRESS_TEXT[s.status] ?? s.status)}</span>}
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
