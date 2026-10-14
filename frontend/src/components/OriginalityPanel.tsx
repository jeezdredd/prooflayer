import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import type { OriginalityMatch, Submission } from "../types";
import { msg, t } from "../i18n";

const KIND_LABEL: Record<OriginalityMatch["kind"], string> = {
  exact: msg("word for word"),
  paraphrase: msg("reworded"),
  translation: msg("translated"),
};

function tone(originality: number) {
  if (originality >= 85) return "text-signal-sage";
  if (originality >= 60) return "text-signal-amber";
  return "text-signal-blood";
}

function SourceTitle({ match }: { match: OriginalityMatch }) {
  if (match.source === "web" && match.url) {
    return (
      <a href={match.url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-ink-100 hover:text-signal-amber break-all">
        {match.title || match.url} <ExternalLink size={11} />
      </a>
    );
  }
  if (match.submission_id) {
    return (
      <Link to={`/results/${match.submission_id}`} className="text-ink-100 hover:text-signal-amber">
        {match.title} {match.author && <span className="text-ink-500">· {match.author}{match.classroom ? `, ${match.classroom}` : ""}</span>}
      </Link>
    );
  }
  return <span className="text-ink-300">{match.title}</span>;
}

export default function OriginalityPanel({ submission }: { submission: Submission }) {
  const report = submission.originality;
  if (!report) return null;

  return (
    <div className="px-6 py-5 border-b border-ink-700">
      <div className="flex items-baseline justify-between gap-4 mb-2">
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("Originality")}</div>
        {report.status === "done" && report.originality != null ? (
          <div className={`font-display text-3xl tabular-nums ${tone(report.originality)}`}>{Math.round(report.originality)}%</div>
        ) : (
          <div className="font-mono text-[11px] text-ink-500">{report.status === "failed" ? t("check failed") : t("checking sources…")}</div>
        )}
      </div>
      {report.status === "done" && (
        <>
          <p className="text-xs text-ink-500 mb-3">
            {report.web_searched ? t("Compared with every work on ProofLayer and the open web, including reworded and translated passages.") : t("Compared with every work on ProofLayer, including reworded and translated passages.")}{" "}
            {t("Quotes with references are fine; judge each match in context.")}
          </p>
          {report.matches.length === 0 ? (
            <p className="text-sm text-signal-sage">{t("No matching sources found.")}</p>
          ) : (
            <div className="divide-y divide-[var(--line-strong)]">
              {report.matches.slice(0, 12).map((m, i) => (
                <details key={i} className="py-3 group">
                  <summary className="cursor-pointer list-none grid grid-cols-[auto_1fr_auto] gap-3 items-baseline">
                    <span className="font-mono text-[11px] tabular-nums text-ink-400 w-12">{m.share}%</span>
                    <span className="text-sm min-w-0"><SourceTitle match={m} /></span>
                    <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
                      {m.source === "web" ? t("web") : "ProofLayer"} · {t(KIND_LABEL[m.kind])}
                    </span>
                  </summary>
                  <div className="mt-2 pl-[3.75rem] space-y-1.5">
                    {m.excerpts.map((e, j) => (
                      <blockquote key={j} className="text-xs text-ink-300 border-l-2 border-signal-amber/50 pl-3 leading-relaxed">{e}</blockquote>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
