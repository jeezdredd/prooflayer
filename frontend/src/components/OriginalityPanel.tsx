import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import type { OriginalityMatch, Submission } from "../types";
import { locale, msg, t } from "../i18n";
import SearchingOrb from "./SearchingOrb";
import { isHiddenSource, isPaper, webScope } from "./TeacherSummary";

const KIND_LABEL: Record<OriginalityMatch["kind"], string> = {
  exact: msg("word for word"),
  paraphrase: msg("reworded"),
  translation: msg("translated"),
};

const PAIRED_MATCHES = 3;

function tone(originality: number) {
  if (originality >= 85) return "text-signal-sage";
  if (originality >= 60) return "text-signal-amber";
  return "text-signal-blood";
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

const SHOWN_AUTHORS = 3;

function paperLine(match: OriginalityMatch): string {
  const authors = match.authors ?? [];
  const total = match.authors_total ?? authors.length;
  const names = authors.slice(0, SHOWN_AUTHORS).join(", ");
  const byline = names && total > SHOWN_AUTHORS ? t("{names} et al.", { names }) : names;
  return [t("Scientific paper"), byline, match.year ? String(match.year) : "", match.venue ?? ""].filter(Boolean).join(" · ");
}

function SourceTitle({ match, student }: { match: OriginalityMatch; student: boolean }) {
  if (match.source === "web" && match.url) {
    return (
      <span className="block">
        <a href={match.url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-ink-50 hover:text-signal-amber break-all">
          {match.title || match.url} <ExternalLink size={11} />
        </a>
        <span className="block text-xs text-ink-500">
          {isPaper(match) ? paperLine(match) : t("Web page · {host}", { host: hostOf(match.url) })}
        </span>
      </span>
    );
  }
  const date = match.submitted_at ? new Date(match.submitted_at).toLocaleDateString(locale()) : "";
  if (!isHiddenSource(match) && match.submission_id) {
    return (
      <span className="block">
        <Link to={`/results/${match.submission_id}`} className="text-ink-50 hover:text-signal-amber">{match.title}</Link>
        <span className="block text-xs text-ink-500">
          {t("Work by {name}", { name: match.author ?? "" })}{match.classroom ? `, ${match.classroom}` : ""}
          {date ? ` · ${date}` : ""}
        </span>
      </span>
    );
  }
  const fromOtherClass = !student && match.hidden_reason !== "student_view";
  return (
    <span className="block">
      <span className="text-ink-50">{t("Another student's work")}</span>
      <span className="block text-xs text-ink-500">
        {date ? t("handed in {date}", { date }) : ""}
        {date && fromOtherClass ? " · " : ""}
        {fromOtherClass && t("from a class you do not teach, so its author and text are hidden")}
      </span>
    </span>
  );
}

function Passages({ match, full }: { match: OriginalityMatch; full: boolean }) {
  const sources = match.source_excerpts ?? [];
  const paired = full && sources.some((s) => s);
  if (match.excerpts.length === 0) return null;
  return (
    <div className="px-3 py-2.5 space-y-2.5">
      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">{paired ? t("Matching passages side by side") : t("Matching passages in this work")}</div>
      {match.excerpts.map((e, j) => (
        <div key={j} className="space-y-1">
          <blockquote className="text-sm text-ink-200 border-l-2 border-signal-amber/60 pl-3 leading-relaxed">
            {paired && <span className="block font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">{t("In the work:")}</span>}
            {e}
          </blockquote>
          {paired && sources[j] && (
            <blockquote className="text-sm text-ink-300 border-l-2 border-ink-500 pl-3 leading-relaxed">
              <span className="block font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">{t("In the source:")}</span>
              {sources[j]}
            </blockquote>
          )}
        </div>
      ))}
      {full && !paired && match.source !== "web" && isHiddenSource(match) && <div className="text-[11px] text-ink-600">{t("The text of the other work is hidden.")}</div>}
    </div>
  );
}

export default function OriginalityPanel({ submission, student = false }: { submission: Submission; student?: boolean }) {
  const report = submission.originality;
  if (!report) return null;

  return (
    <div className="px-6 py-5 border-b border-ink-700">
      <div className={`flex justify-between gap-4 mb-2 ${report.status === "done" && report.originality != null ? "items-baseline" : "items-center"}`}>
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("Originality")}</div>
        {report.status === "done" && report.originality != null ? (
          <div className={`font-display text-3xl tabular-nums ${tone(report.originality)}`}>{Math.round(report.originality)}%</div>
        ) : (
          report.status === "failed" ? (
            <div className="font-mono text-[11px] text-ink-500">{t("check failed")}</div>
          ) : (
            <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.06] bg-white/[0.04] py-1 pl-1.5 pr-3 font-mono text-[11px] text-ink-400">
              <SearchingOrb size={22} />
              <span className="shimmer-text">{t("checking sources…")}</span>
            </div>
          )
        )}
      </div>
      {report.status === "done" && (
        <>
          {report.originality != null && report.matches.length > 0 && (
            <p className="text-sm text-ink-200 mb-1">
              {100 - Math.round(report.originality) < 1
                ? t("Less than 1% of the text matches the sources below.")
                : t("{own}% of the text was not found anywhere; {copied}% matches the sources below.", { own: Math.round(report.originality), copied: 100 - Math.round(report.originality) })}
            </p>
          )}
          <p className="text-xs text-ink-500 mb-3">
            {webScope(report)} {t("Reworded and translated passages count too.")}{" "}
            {student ? t("Quotes with references are fine.") : t("Quotes with references are fine; judge each match in context.")}
          </p>
          {report.matches.length === 0 ? (
            <p className="text-sm text-signal-sage">{t("No matching sources found.")}</p>
          ) : (
            <div className="space-y-3">
              {report.matches.slice(0, 12).map((m, i) => (
                <div key={i} className="border border-[var(--line-strong)]">
                  <div className="grid grid-cols-[auto_1fr] gap-3 items-start px-3 py-2.5 border-b border-[var(--line)]">
                    <span className="font-display text-xl tabular-nums text-signal-amber w-14">{Math.round(m.share) < 1 ? "<1" : Math.round(m.share)}%</span>
                    <span className="min-w-0">
                      <span className="block font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 mb-0.5">{t("Source")} · {t(KIND_LABEL[m.kind])}</span>
                      <SourceTitle match={m} student={student} />
                    </span>
                  </div>
                  <Passages match={m} full={i < PAIRED_MATCHES} />
                </div>
              ))}
              <p className="text-[11px] text-ink-600">{t("The percentage is the share of this work's text found in that source.")}</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
