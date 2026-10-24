import clsx from "clsx";
import type { AnalysisResult, Submission } from "../types";
import { t } from "../i18n";
import { STATUS_TEXT, plainOutcome, type CheckStatus } from "./TeacherSummary";
import { isImage } from "./resultView";

const IMAGE_DETECTORS = ["community_forensics", "ai_detector", "clip_probe", "custom_detector", "npr_detector", "siglip_detector", "llm_vision"];

const BAR: Record<CheckStatus, string> = {
  ok: "border-signal-sage",
  look: "border-signal-amber",
  alert: "border-signal-blood",
  wait: "border-ink-500",
  off: "border-ink-600",
};

function byName(submission: Submission, name: string): AnalysisResult | undefined {
  return submission.analysis_results.find((r) => r.analyzer_name === name);
}

export function hasProvenanceProof(submission: Submission): boolean {
  return byName(submission, "metadata")?.evidence?.provenance_proof === true;
}

function detectorLine(submission: Submission): string | null {
  const voters = submission.analysis_results.filter((r) => IMAGE_DETECTORS.includes(r.analyzer_name) && r.verdict !== "error");
  if (voters.length === 0) return null;
  const forAi = voters.filter((r) => r.verdict === "fake" || r.verdict === "suspicious").length;
  return t("AI detectors: {n} of {total} vote for AI.", { n: forAi, total: voters.length });
}

function visionLine(submission: Submission): string | null {
  const ev = byName(submission, "llm_vision")?.evidence;
  if (!ev || ev.llm_verdict !== "ai_generated" || typeof ev.reasoning !== "string" || !ev.reasoning) return null;
  return t("What the model noticed: \"{reasoning}\". This is a hint where to look, not proof.", { reasoning: ev.reasoning });
}

function editLine(submission: Submission): string | null {
  const ev = byName(submission, "ela")?.evidence;
  if (!ev || ev.source_format !== "JPEG" || ev.manipulation_suspected !== true) return null;
  return t("Some areas may have been pasted in from another picture.");
}

function nextStep(status: CheckStatus, proof: boolean): string {
  if (proof) return t("Next step: discuss with the student whether AI pictures were allowed in this task.");
  if (status === "alert" || status === "look") {
    return t("Next step: ask the student how they made the picture and for the original file or drafts. A flag is a reason to ask, not proof.");
  }
  if (status === "ok") return t("Nothing to do.");
  return t("Next step: look at the work yourself; the checks gave no clear answer.");
}

export default function MediaSummary({ submission, student }: { submission: Submission; student: boolean }) {
  if (submission.status !== "completed") return null;
  const proof = hasProvenanceProof(submission);
  const outcome = plainOutcome(submission.final_verdict, null, null, student);
  const lines = isImage(submission)
    ? [proof ? t("Made by AI: the invisible mark in the file proves it.") : detectorLine(submission), visionLine(submission), editLine(submission)].filter(
        (line): line is string => !!line,
      )
    : [];

  return (
    <section className="px-4 sm:px-6 py-5 border-b border-ink-700">
      <div className={clsx("border-l-4 pl-4 py-1", BAR[outcome.status])}>
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("In short")}</div>
        <h3 className={clsx("font-display text-2xl sm:text-3xl leading-tight mt-1", STATUS_TEXT[outcome.status])}>{t(outcome.text)}</h3>
        {lines.map((line) => (
          <p key={line} className="text-sm text-ink-200 mt-2 leading-relaxed">{line}</p>
        ))}
        {!student && <p className="text-sm text-ink-100 mt-2 leading-relaxed">{nextStep(outcome.status, proof)}</p>}
        <p className="text-xs text-ink-500 mt-3">
          {proof
            ? t("The mark is put there by the AI generator itself. What to do with the work is up to the teacher.")
            : t("The checks give hints, not proof. The teacher makes the decision.")}
        </p>
      </div>
    </section>
  );
}
