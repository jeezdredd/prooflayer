import { Link } from "react-router-dom";
import { useProvenance } from "../hooks/useProvenance";
import type { ProvenanceMatch, ProvenanceResult, Submission } from "../types";
import { msg, t } from "../i18n";
import { isClassView, isStudentView, longDate } from "./resultView";

const WHAT: Record<ProvenanceMatch["kind"], string> = {
  same: msg("The same picture"),
  near: msg("An almost identical picture"),
  similar: msg("A picture with similar content"),
};

const WHERE: Record<ProvenanceMatch["scope"] | "yours_class", string> = {
  visible: msg("{what} was handed in: {who}"),
  yours: msg("{what} was checked by you before: {who}"),
  yours_class: msg("{what} you already handed in: {who}"),
  same_class: msg("{what} was handed in by another student of this class"),
  same_school: msg("{what} was handed in to another class of your school"),
  elsewhere: msg("{what} was already checked on ProofLayer"),
};

function matchLine(row: ProvenanceResult, match: ProvenanceMatch, student: boolean): string {
  const first = match.scope === "yours" ? row.title : match.author;
  const who = [first, match.classroom, longDate(match.submitted_at)].filter(Boolean).join(", ");
  const scope = match.scope === "yours" && student ? "yours_class" : match.scope;
  return t(WHERE[scope], { what: t(WHAT[match.kind]), who });
}

function emptyText(submission: Submission): string {
  if (isStudentView(submission)) return t("No other work has the same picture.");
  if (isClassView(submission)) return t("None of the work in your classes has the same picture.");
  return t("No similar pictures among your checks and the public feed.");
}

function InternalRow({ row, match, student }: { row: ProvenanceResult; match: ProvenanceMatch; student: boolean }) {
  return (
    <div className="border-l-2 border-signal-amber/60 pl-3 py-1">
      <p className="text-sm text-ink-100 leading-snug">{matchLine(row, match, student)}</p>
      <div className="flex items-center gap-3 mt-1">
        {row.is_sensitive && (
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-signal-amber border border-signal-amber/40 px-2 py-0.5">
            {t("Sensitive")}
          </span>
        )}
        {match.submission_id && (
          <Link to={`/results/${match.submission_id}`} className="text-xs text-iris hover:text-iris-light transition">
            {t("Open that work")} &rarr;
          </Link>
        )}
      </div>
    </div>
  );
}

function ExternalRow({ row }: { row: ProvenanceResult }) {
  return (
    <div className="border-l-2 border-ink-600 pl-3 py-1">
      <p className="text-sm text-ink-100 leading-snug">
        {t("Found on the web: {title}", { title: row.title || row.source_url })}
        {row.similarity_score !== null && row.similarity_score <= 1 && (
          <span className="text-ink-400"> · {t("{n}% similar", { n: (row.similarity_score * 100).toFixed(0) })}</span>
        )}
      </p>
      {row.source_url && (
        <a href={row.source_url} target="_blank" rel="noopener noreferrer" className="text-xs text-iris hover:text-iris-light truncate block transition">
          {row.source_url}
        </a>
      )}
    </div>
  );
}

export default function ProvenancePanel({ submission }: { submission: Submission }) {
  const { data: results, isLoading } = useProvenance(submission.id);
  const rows = (results ?? []).filter((r) => r.match || r.source_url);
  const student = isStudentView(submission);

  return (
    <div className="case-card p-6 mt-4">
      <h4 className="label-mono mb-3">{t("Where else this picture appears")}</h4>
      {isLoading ? (
        <p className="text-sm text-ink-500">{t("Checking sources...")}</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-ink-300">{emptyText(submission)}</p>
      ) : (
        <div className="space-y-3">
          {rows.map((row) =>
            row.match ? <InternalRow key={row.id} row={row} match={row.match} student={student} /> : <ExternalRow key={row.id} row={row} />,
          )}
        </div>
      )}
    </div>
  );
}
