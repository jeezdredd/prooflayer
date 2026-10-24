import clsx from "clsx";
import { useAuthStore } from "../stores/authStore";
import type { Submission } from "../types";
import { t } from "../i18n";
import { canAnswerObjection, longDate } from "./resultView";

const TONE: Record<string, string> = {
  amber: "border-signal-amber bg-signal-amber/5 text-signal-amber",
  blood: "border-signal-blood bg-signal-blood/5 text-signal-blood",
  sage: "border-signal-sage bg-signal-sage/5 text-signal-sage",
  ink: "border-ink-500 bg-ink-800/40 text-ink-200",
};

function scrollToObjection() {
  document.getElementById("objection")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function bannerFor(submission: Submission, isStaff: boolean): { text: string; action: string; tone: string } | null {
  const objection = submission.objection;
  if (!objection) return null;
  const author = submission.viewer_role === "author";
  const inClass = !!submission.in_class;
  if (objection.status === "open") {
    if (canAnswerObjection(submission, isStaff)) {
      const text = inClass
        ? t("The student objected to the verdict. Please answer by {date}.", { date: longDate(objection.due_at) })
        : t("The author objected to the verdict. Please answer by {date}.", { date: longDate(objection.due_at) });
      return {
        text: objection.overdue ? `${text} ${t("The deadline has passed.")}` : text,
        action: t("Answer"),
        tone: objection.overdue ? "blood" : "amber",
      };
    }
    if (!author) return null;
    return {
      text: inClass
        ? t("You objected to the verdict on {date}. Your teacher will answer by {due}.", { date: longDate(objection.created_at), due: longDate(objection.due_at) })
        : t("You objected to the verdict on {date}. A reviewer will answer by {due}.", { date: longDate(objection.created_at), due: longDate(objection.due_at) }),
      action: t("Read your objection"),
      tone: "amber",
    };
  }
  const date = longDate(objection.responded_at);
  const changed = objection.decision === "changed";
  if (author) {
    return {
      text: changed
        ? t("Your objection was accepted on {date}: the work counts as your own.", { date })
        : t("Your objection was reviewed on {date} and the verdict was kept.", { date }),
      action: t("Read the answer"),
      tone: changed ? "sage" : "ink",
    };
  }
  return {
    text: changed
      ? t("The verdict was changed after the student's objection on {date}: the work counts as the student's own.", { date })
      : t("The verdict was kept after the student's objection on {date}.", { date }),
    action: t("Read the answer"),
    tone: changed ? "sage" : "ink",
  };
}

export default function ObjectionBanner({ submission }: { submission: Submission }) {
  const isStaff = !!useAuthStore((s) => s.user?.is_staff);
  if (submission.status !== "completed") return null;
  const banner = bannerFor(submission, isStaff);
  if (!banner) return null;
  return (
    <div className={clsx("mb-4 border-l-4 px-4 py-3 flex flex-wrap items-center justify-between gap-3", TONE[banner.tone])}>
      <p className="text-sm leading-snug text-ink-50">{banner.text}</p>
      <button
        type="button"
        onClick={scrollToObjection}
        className="font-mono text-[11px] uppercase tracking-[0.14em] border border-current px-3 py-1.5 hover:bg-white/5 shrink-0"
      >
        {banner.action}
      </button>
    </div>
  );
}
