import clsx from "clsx";
import type { AnalysisResult, Submission } from "../types";
import { msg, t } from "../i18n";
import { PLAIN_VERDICT, STATUS_TEXT, type CheckStatus } from "./TeacherSummary";
import { elaWorksOn, readableReasoning } from "./resultView";

type Evidence = Record<string, unknown>;
type MediaKind = "image" | "audio" | "video";

const AI_VERDICTS = ["fake", "likely_fake"];
const MEDIA_DETECTORS = ["community_forensics", "ai_detector", "clip_probe", "custom_detector", "npr_detector", "siglip_detector", "llm_vision", "audio_spectrogram", "video_frame"];
const FLAGGED = new Set(["fake", "likely_fake", "suspicious"]);
const VOTED = new Set(["fake", "likely_fake", "suspicious", "authentic", "authentic_edited"]);

const BAR: Record<CheckStatus, string> = {
  ok: "border-signal-sage",
  look: "border-signal-amber",
  alert: "border-signal-blood",
  wait: "border-ink-500",
  off: "border-ink-600",
};

const MEDIA_MADE: Record<MediaKind, string> = {
  image: msg("The picture was made by an AI generator"),
  audio: msg("The recording was made by an AI generator"),
  video: msg("The video was made by an AI generator"),
};

const MEDIA_LIKELY: Record<MediaKind, string> = {
  image: msg("Looks like an AI-made picture"),
  audio: msg("Looks like an AI-made recording"),
  video: msg("Looks like an AI-made video"),
};

const MEDIA_NEXT: Record<MediaKind, string> = {
  image: msg("Next step: ask the student to show the original photo on their phone (with its date and place) or drafts of the drawing. A flag is a reason to ask, not proof."),
  audio: msg("Next step: ask the student to show the original recording and how they made it. A flag is a reason to ask, not proof."),
  video: msg("Next step: ask the student to show the original video and how they made it. A flag is a reason to ask, not proof."),
};

function byName(submission: Submission, name: string): AnalysisResult | undefined {
  return submission.analysis_results.find((r) => r.analyzer_name === name);
}

function mediaKind(submission: Submission): MediaKind | null {
  if (submission.mime_type?.startsWith("image/")) return "image";
  if (submission.mime_type?.startsWith("audio/")) return "audio";
  if (submission.mime_type?.startsWith("video/")) return "video";
  return null;
}

export function hasProvenanceProof(submission: Submission): boolean {
  return byName(submission, "metadata")?.evidence?.provenance_proof === true;
}

function generatorName(meta: Evidence): string | null {
  const mark = meta.watermark as Evidence | null | undefined;
  if (mark && typeof mark.name === "string") return mark.name;
  const trace = (meta.ai_trace as Evidence[] | undefined) ?? [];
  const named = trace.find((x) => typeof x.generator === "string" && x.generator);
  return named ? String(named.generator) : null;
}

function markLine(submission: Submission): string {
  const generator = generatorName(byName(submission, "metadata")?.evidence ?? {});
  return generator
    ? t("The file carries an invisible mark from {generator}. Phones and cameras do not add such a mark.", { generator })
    : t("The file carries an invisible mark of an AI generator. Phones and cameras do not add such a mark.");
}

function outcomeFor(submission: Submission, kind: MediaKind, proof: boolean, student: boolean): { text: string; status: CheckStatus; tally?: string } {
  const verdict = submission.final_verdict;
  const votes = MEDIA_DETECTORS.map((name) => byName(submission, name)).filter((r): r is AnalysisResult => !!r && VOTED.has(r.verdict));
  const flagged = votes.filter((r) => FLAGGED.has(r.verdict)).length;
  const tally = flagged > 0 ? t("Checks that think so: {n} of {m}.", { n: flagged, m: votes.length }) : undefined;
  if (proof) return { text: student ? t(PLAIN_VERDICT.fake.student) : t(MEDIA_MADE[kind]), status: "alert" };
  if (student) {
    const base = PLAIN_VERDICT[verdict] ?? PLAIN_VERDICT.inconclusive;
    return { text: t(base.student), status: base.status };
  }
  if (AI_VERDICTS.includes(verdict)) return { text: t(MEDIA_LIKELY[kind]), status: "alert", tally };
  if (verdict === "suspicious" || verdict === "needs_review") return { text: t("Worth a closer look"), status: "look", tally };
  if (verdict === "authentic" || verdict === "authentic_edited") return { text: t("No signs of an AI generator found"), status: "ok" };
  return {
    text: t("No clear answer"),
    status: "wait",
    tally: flagged > 0 && flagged < votes.length ? t("The checks disagree: {n} of {m} see signs of an AI generator.", { n: flagged, m: votes.length }) : undefined,
  };
}

function visionLine(submission: Submission): string | null {
  const ev = byName(submission, "llm_vision")?.evidence;
  const reasoning = ev?.llm_verdict === "ai_generated" ? readableReasoning(ev) : null;
  if (!reasoning) return null;
  return t("What the model noticed: \"{reasoning}\". This is a hint where to look, not proof.", { reasoning });
}

function editLine(submission: Submission): string | null {
  const ev = byName(submission, "ela")?.evidence;
  if (!ev || !elaWorksOn(ev) || ev.manipulation_suspected !== true) return null;
  return t("Some areas may have been pasted in from another picture.");
}

function nextStep(status: CheckStatus, kind: MediaKind, proof: boolean): string {
  if (proof) return t("Next step: discuss with the student whether AI pictures were allowed in this task.");
  if (status === "alert" || status === "look") return t(MEDIA_NEXT[kind]);
  if (status === "ok") return t("Nothing to do.");
  return t("Next step: look at the work yourself; the checks gave no clear answer.");
}

export default function MediaSummary({ submission, student }: { submission: Submission; student: boolean }) {
  const kind = mediaKind(submission);
  if (submission.status !== "completed" || !kind || !submission.analysis_results?.length) return null;
  const proof = hasProvenanceProof(submission) && AI_VERDICTS.includes(submission.final_verdict);
  const outcome = outcomeFor(submission, kind, proof, student);
  const lines = [
    proof ? markLine(submission) : outcome.tally,
    kind === "image" && !student ? visionLine(submission) : null,
    kind === "image" && !student ? editLine(submission) : null,
  ].filter((line): line is string => !!line);

  return (
    <section className="px-4 sm:px-6 py-5 border-b border-ink-700">
      <div className={clsx("border-l-4 pl-4 py-1", BAR[outcome.status])}>
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("In short")}</div>
        <h3 className={clsx("font-display text-2xl sm:text-3xl leading-tight mt-1", STATUS_TEXT[outcome.status])}>{outcome.text}</h3>
        {lines.map((line) => (
          <p key={line} className="text-sm text-ink-200 mt-2 leading-relaxed">{line}</p>
        ))}
        {!student && <p className="text-sm text-ink-100 mt-2 leading-relaxed">{nextStep(outcome.status, kind, proof)}</p>}
        <p className="text-xs text-ink-500 mt-3">
          {proof
            ? t("The mark is put there by the AI generator itself. What to do with the work is up to the teacher.")
            : t("The checks give hints, not proof. The teacher makes the decision.")}
        </p>
      </div>
    </section>
  );
}
