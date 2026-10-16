import clsx from "clsx";
import type { AnalysisResult, Submission } from "../types";
import { msg, t, tn } from "../i18n";

type Evidence = Record<string, unknown>;
export type CheckStatus = "ok" | "look" | "alert" | "wait" | "off";

export interface Check {
  key: string;
  title: string;
  status: CheckStatus;
  headline: string;
  detail?: string;
}

const TEXT_ANALYZERS = ["text_classifier", "text_evasion", "text_grade_fit", "text_style", "text_citations", "text_shadow"];
const FLAGGED = new Set(["fake", "likely_fake", "suspicious"]);
const AI_LOOK = 0.45;
const SPREAD_ALERT = 0.5;

const STATUS_STYLE: Record<CheckStatus, { word: string; tile: string; chip: string; dot: string; bar: string; text: string }> = {
  ok: { word: msg("Clear"), tile: "border-signal-sage/40", chip: "bg-signal-sage/15 text-signal-sage", dot: "bg-signal-sage", bar: "border-signal-sage", text: "text-signal-sage" },
  look: { word: msg("Look closer"), tile: "border-signal-amber/50 bg-signal-amber/5", chip: "bg-signal-amber/15 text-signal-amber", dot: "bg-signal-amber", bar: "border-signal-amber", text: "text-signal-amber" },
  alert: { word: msg("Flag"), tile: "border-signal-blood/60 bg-signal-blood/5", chip: "bg-signal-blood/15 text-signal-blood", dot: "bg-signal-blood", bar: "border-signal-blood", text: "text-signal-blood" },
  wait: { word: msg("Needs more work"), tile: "border-[var(--line-strong)]", chip: "bg-ink-800 text-ink-300", dot: "bg-ink-500", bar: "border-ink-500", text: "text-ink-300" },
  off: { word: msg("Not checked"), tile: "border-[var(--line-strong)] opacity-70", chip: "bg-ink-800 text-ink-500", dot: "bg-ink-600", bar: "border-ink-600", text: "text-ink-400" },
};

function byName(submission: Submission, name: string): AnalysisResult | undefined {
  return submission.analysis_results?.find((r) => r.analyzer_name === name);
}

function evidence(result: AnalysisResult | undefined): Evidence {
  return (result?.evidence ?? {}) as Evidence;
}

export function isTextSubmission(submission: Submission): boolean {
  return TEXT_ANALYZERS.some((name) => byName(submission, name));
}

function aiCheck(submission: Submission): Check | null {
  const result = byName(submission, "text_classifier");
  if (!result) return null;
  const ev = evidence(result);
  const title = t("AI writing");
  const p = typeof ev.ai_probability === "number" ? ev.ai_probability : null;
  if (p === null) return { key: "ai", title, status: "off", headline: t("Could not score this text") };
  const score = Math.round(p * 100);
  const uneven = typeof ev.segment_spread === "number" && ev.segment_spread >= SPREAD_ALERT;
  const unevenNote = uneven ? ` ${t("Some passages read far more machine-like than the rest.")}` : "";
  if (FLAGGED.has(result.verdict)) {
    return {
      key: "ai",
      title,
      status: "alert",
      headline: t("Reads like chatbot writing"),
      detail: t("Scored {n} out of 100 towards machine writing, above the flag line that only about 1 in 100 texts written by people cross.", { n: score }) + unevenNote,
    };
  }
  if (p >= AI_LOOK || uneven) {
    return {
      key: "ai",
      title,
      status: "look",
      headline: uneven ? t("Parts may be machine-written") : t("Some machine-like writing"),
      detail: t("Scored {n} out of 100 towards machine writing, below the flag line.", { n: score }) + unevenNote,
    };
  }
  return { key: "ai", title, status: "ok", headline: t("Reads like a person's writing"), detail: t("Scored {n} out of 100 towards machine writing.", { n: score }) };
}

function copyCheck(submission: Submission): Check | null {
  const report = submission.originality;
  if (!report) return null;
  const title = t("Copying");
  if (report.status === "failed") return { key: "copy", title, status: "off", headline: t("Copy check failed") };
  if (report.status !== "done" || report.originality == null) return { key: "copy", title, status: "wait", headline: t("Still comparing with other work") };
  const scope = report.web_searched
    ? t("Compared with every work on ProofLayer and the open web.")
    : t("Compared with every work on ProofLayer; web search is off for this school.");
  const matched = 100 - Math.round(report.originality);
  if (report.matches.length === 0) return { key: "copy", title, status: "ok", headline: t("No copied passages found"), detail: scope };
  const status: CheckStatus = report.originality >= 85 ? "ok" : report.originality >= 60 ? "look" : "alert";
  return {
    key: "copy",
    title,
    status,
    headline: t("{n}% matches other work", { n: matched }),
    detail: `${tn(report.matches.length, "Found in {n} source.", "Found in {n} sources.")} ${t("Quotes with references are fine; open each match below to judge it.")}`,
  };
}

function trickCheck(submission: Submission): Check | null {
  const result = byName(submission, "text_evasion");
  if (!result) return null;
  const title = t("Hidden tricks");
  if (result.verdict === "fake" || result.verdict === "suspicious") {
    return {
      key: "tricks",
      title,
      status: "alert",
      headline: t("Attempt to hide AI traces"),
      detail: t("Look-alike letters or punctuation, stray accents, invisible characters or hidden text, the tricks AI humanizers use. Details below."),
    };
  }
  return { key: "tricks", title, status: "ok", headline: t("No disguised letters or hidden text") };
}

export function levelName(level: number): string {
  return level <= 11 ? t("grade {n}", { n: level }) : t("university year {n}", { n: level - 11 });
}

function ageCheck(submission: Submission): Check | null {
  const result = byName(submission, "text_grade_fit");
  if (!result) return null;
  const ev = evidence(result);
  const title = t("Age fit");
  const level = typeof ev.level === "number" ? levelName(ev.level) : t("the class year");
  const baseline = ev.baseline as { have: number; need: number } | undefined;
  if (result.verdict === "suspicious") {
    return {
      key: "age",
      title,
      status: "look",
      headline: t("Vocabulary well above {level}", { level }),
      detail: t("Also above this student's own earlier work. Words unusual at this age are listed below."),
    };
  }
  if (baseline && baseline.have < baseline.need) {
    return {
      key: "age",
      title,
      status: "wait",
      headline: t("Above {level}, too early to judge", { level }),
      detail: t("Strong students are compared with their own level. {have} of {need} earlier works so far.", { have: baseline.have, need: baseline.need }),
    };
  }
  if (baseline) return { key: "age", title, status: "ok", headline: t("Above {level}, usual for this student", { level }) };
  if (ev.reason === "class level not set") {
    return { key: "age", title, status: "off", headline: t("Class year not set"), detail: t("Set the class year in class settings to compare vocabulary with the students' age.") };
  }
  if (typeof ev.reason === "string") return { key: "age", title, status: "off", headline: t(ev.reason) };
  return { key: "age", title, status: "ok", headline: t("Vocabulary fits {level}", { level }) };
}

function styleCheck(submission: Submission): Check | null {
  const result = byName(submission, "text_style");
  if (!result) return null;
  const ev = evidence(result);
  const title = t("Own style");
  const drift = ev.drift as { history_size: number } | undefined;
  const baseline = ev.baseline as { have: number; need: number } | undefined;
  if (result.verdict === "suspicious") {
    return {
      key: "style",
      title,
      status: "look",
      headline: t("Writes differently from earlier work"),
      detail: tn(drift?.history_size ?? 0, "Compared with {n} earlier work in this class.", "Compared with {n} earlier works in this class."),
    };
  }
  if (drift) {
    return {
      key: "style",
      title,
      status: "ok",
      headline: t("Matches the student's earlier work"),
      detail: tn(drift.history_size, "Compared with {n} earlier work.", "Compared with {n} earlier works."),
    };
  }
  return {
    key: "style",
    title,
    status: "wait",
    headline: t("{have} of {need} earlier works so far", { have: baseline?.have ?? 0, need: baseline?.need ?? 3 }),
    detail: t("A student is only compared with themselves once there is enough of their work, so nobody is flagged on their first pieces."),
  };
}

function sourceCheck(submission: Submission): Check | null {
  const result = byName(submission, "text_citations");
  if (!result) return null;
  const ev = evidence(result);
  const title = t("Sources");
  const refs = (ev.references as { status: string }[] | undefined) ?? [];
  const missing = refs.filter((r) => r.status === "missing").length;
  const found = refs.filter((r) => r.status === "found").length;
  if (refs.length === 0) {
    if (ev.genre === "report") return { key: "sources", title, status: "look", headline: t("Research text with no sources") };
    return { key: "sources", title, status: "off", headline: t("No sources cited") };
  }
  if (result.verdict === "suspicious") {
    return {
      key: "sources",
      title,
      status: "alert",
      headline: t("{missing} of {total} sources do not seem to exist", { missing, total: refs.length }),
      detail: t("Invented references are a common trace of chatbot writing. The list is below."),
    };
  }
  if (missing > 0) return { key: "sources", title, status: "look", headline: t("{missing} of {total} sources not found", { missing, total: refs.length }) };
  if (found > 0) return { key: "sources", title, status: "ok", headline: tn(found, "The cited source exists", "All {n} sources exist") };
  return { key: "sources", title, status: "off", headline: t("Sources could not be checked right now") };
}

function shadowCheck(submission: Submission): Check | null {
  const result = byName(submission, "text_shadow");
  if (!result) return null;
  const ev = evidence(result);
  const title = t("AI answers to the task");
  if (typeof ev.share !== "number") {
    if (ev.reason === "not a class submission") return null;
    return {
      key: "shadow",
      title,
      status: "off",
      headline: t("No AI answers generated yet"),
      detail: t("Generate AI answers to the assignment on the class page to compare student work with them."),
    };
  }
  if (result.verdict === "suspicious") {
    return { key: "shadow", title, status: "alert", headline: t("Follows an AI answer: {n}% of sentences, same order", { n: Math.round(ev.share * 100) }) };
  }
  return { key: "shadow", title, status: "ok", headline: t("Different from AI answers to this task") };
}

export function textChecks(submission: Submission): Check[] {
  return [aiCheck, copyCheck, trickCheck, ageCheck, styleCheck, sourceCheck, shadowCheck]
    .map((fn) => fn(submission))
    .filter((c): c is Check => c !== null);
}

export const PLAIN_VERDICT: Record<string, { teacher: string; student: string; status: CheckStatus }> = {
  authentic: { teacher: msg("Looks like the student's own work"), student: msg("Your work passed the checks"), status: "ok" },
  authentic_edited: { teacher: msg("Looks like the student's own work"), student: msg("Your work passed the checks"), status: "ok" },
  needs_review: { teacher: msg("Worth a closer look"), student: msg("Your teacher may ask you about this work"), status: "look" },
  suspicious: { teacher: msg("Worth a conversation with the student"), student: msg("Your teacher may ask you about this work"), status: "look" },
  likely_fake: { teacher: msg("Strong signs the student did not write this"), student: msg("Your teacher will want to talk about this work"), status: "alert" },
  fake: { teacher: msg("Strong signs the student did not write this"), student: msg("Your teacher will want to talk about this work"), status: "alert" },
  inconclusive: { teacher: msg("No clear answer"), student: msg("No clear answer yet"), status: "wait" },
};

export const STATUS_TEXT: Record<CheckStatus, string> = Object.fromEntries(
  Object.entries(STATUS_STYLE).map(([k, v]) => [k, v.text]),
) as Record<CheckStatus, string>;

function Tile({ check }: { check: Check }) {
  const s = STATUS_STYLE[check.status];
  return (
    <div className={clsx("border p-3.5 flex flex-col gap-1.5", s.tile)}>
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400">{check.title}</span>
        <span className={clsx("font-mono text-[10px] uppercase tracking-[0.12em] px-1.5 py-0.5 flex items-center gap-1.5 shrink-0", s.chip)}>
          <span className={clsx("w-1.5 h-1.5 rounded-full", s.dot)} />
          {t(s.word)}
        </span>
      </div>
      <div className="text-sm text-ink-50 leading-snug">{check.headline}</div>
      {check.detail && <div className="text-xs text-ink-400 leading-relaxed">{check.detail}</div>}
    </div>
  );
}

function lowerFirst(s: string): string {
  return s.charAt(0).toLowerCase() + s.slice(1);
}

export default function TeacherSummary({ submission, student }: { submission: Submission; student: boolean }) {
  if (submission.status !== "completed" || !isTextSubmission(submission)) return null;
  const checks = textChecks(submission);
  const plain = PLAIN_VERDICT[submission.final_verdict] ?? PLAIN_VERDICT.inconclusive;
  const tone = STATUS_STYLE[plain.status];
  const raised = checks.filter((c) => c.status === "alert" || c.status === "look");
  const waiting = checks.filter((c) => c.status === "wait");
  const waitingNote = student
    ? tn(waiting.length, "{n} check will say more once there is more of your work.", "{n} checks will say more once there is more of your work.")
    : tn(waiting.length, "{n} check will say more once there is more of this student's work.", "{n} checks will say more once there is more of this student's work.");

  return (
    <section className="px-4 sm:px-6 py-5 border-b border-ink-700">
      <div className={clsx("border-l-4 pl-4 py-1", tone.bar)}>
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("In short")}</div>
        <h3 className={clsx("font-display text-2xl sm:text-3xl leading-tight mt-1", tone.text)}>{t(student ? plain.student : plain.teacher)}</h3>
        <p className="text-sm text-ink-300 mt-2 leading-relaxed">
          {raised.length > 0 ? t("Raised by: {reasons}.", { reasons: raised.map((c) => lowerFirst(c.headline)).join("; ") }) : t("No check raised a concern.")}
          {waiting.length > 0 && ` ${waitingNote}`}
        </p>
        {!student && raised.length > 0 && (
          <p className="text-sm text-ink-100 mt-2 leading-relaxed">
            {t("Next step: ask the student to talk you through how they wrote it, or to explain a passage in their own words. A flag is a reason to ask, not proof.")}
          </p>
        )}
      </div>
      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3 mt-5">
        {checks.map((c) => <Tile key={c.key} check={c} />)}
      </div>
    </section>
  );
}
