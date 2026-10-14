import type { AnalysisResult, Submission } from "../types";
import { currentLang, msg, t } from "../i18n";
import { levelName } from "./TeacherSummary";

type Evidence = Record<string, unknown>;

function byName(submission: Submission, name: string): AnalysisResult | undefined {
  return submission.analysis_results?.find((r) => r.analyzer_name === name);
}

function Row({ tone, title, children }: { tone: "alert" | "ok" | "muted"; title: string; children?: React.ReactNode }) {
  const dot = tone === "alert" ? "bg-signal-blood" : tone === "ok" ? "bg-signal-sage" : "bg-ink-600";
  return (
    <div className="py-3 grid grid-cols-[auto_1fr] gap-3">
      <span className={`mt-1.5 w-1.5 h-1.5 rounded-full ${dot}`} />
      <div>
        <div className="text-sm text-ink-100">{title}</div>
        {children && <div className="mt-1 text-xs text-ink-400 leading-relaxed">{children}</div>}
      </div>
    </div>
  );
}

function Chips({ items }: { items: string[] }) {
  return (
    <span className="flex flex-wrap gap-1.5 mt-1.5">
      {items.map((w) => (
        <span key={w} className="font-mono text-[11px] px-1.5 py-0.5 border border-[var(--line-strong)] text-ink-200">{w}</span>
      ))}
    </span>
  );
}

interface Reference {
  kind: string;
  value: string;
  status: "found" | "missing" | "unchecked";
  detail: string;
}

interface CitationFormat {
  style: string | null;
  label: string;
  entries: { entry: string; style: string | null; issues: string[] }[];
  issues: string[];
  issue_count: number;
}

const SEGMENT_SPREAD_ALERT = 0.5;

const KIND_LABEL: Record<string, string> = {
  doi: "DOI",
  arxiv: "arXiv",
  isbn: "ISBN",
  url: msg("Link"),
  bibliography: msg("Reference"),
  quote: msg("Quote"),
};

function MissingList({ items }: { items: Reference[] }) {
  return (
    <ul className="mt-1 space-y-1">
      {items.slice(0, 6).map((r) => (
        <li key={`${r.kind}:${r.value}`} className="break-words">
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500 mr-2">{KIND_LABEL[r.kind] ? t(KIND_LABEL[r.kind]) : r.kind}</span>
          <span className="text-ink-200">{r.value}</span>
          {r.detail && <span className="text-ink-500"> ({t(r.detail)})</span>}
        </li>
      ))}
    </ul>
  );
}

export default function TextReport({ submission }: { submission: Submission }) {
  const evasion = byName(submission, "text_evasion");
  const grade = byName(submission, "text_grade_fit");
  const style = byName(submission, "text_style");
  const citations = byName(submission, "text_citations");
  const genre = byName(submission, "text_genre");
  const shadow = byName(submission, "text_shadow");
  const classifierResult = byName(submission, "text_classifier");
  if (!evasion && !grade && !style && !citations && !genre && !shadow && !classifierResult) return null;
  const cl = (classifierResult?.evidence ?? {}) as Evidence;
  const segments = (cl.segments as { excerpt: string; ai_probability: number }[] | undefined) ?? [];
  const spread = typeof cl.segment_spread === "number" ? cl.segment_spread : 0;
  const sh = (shadow?.evidence ?? {}) as Evidence;
  const shadowPairs = (sh.pairs as { student: string; ai: string; similarity: number }[] | undefined) ?? [];
  const ge = (genre?.evidence ?? {}) as Evidence;
  const gr = (grade?.evidence ?? {}) as Evidence;

  const level = typeof gr.level === "number" ? levelName(gr.level) : t("the class level");
  const ev = (evasion?.evidence ?? {}) as Evidence;
  const st = (style?.evidence ?? {}) as Evidence;
  const mixed = (ev.mixed_script_words as string[] | undefined) ?? [];
  const invisible = Object.entries((ev.invisible_characters as Record<string, number> | undefined) ?? {});
  const hidden = (ev.hidden_runs as { text: string; reasons: string[] }[] | undefined) ?? [];
  const beyond = (gr.beyond_level_words as string[] | undefined) ?? [];
  const phrases = Object.keys(((st.phrasebook as Evidence | undefined)?.hits as Record<string, number> | undefined) ?? {});
  const drift = st.drift as { score: number; history_size: number } | undefined;
  const gradeBaseline = gr.baseline as { have: number; need: number } | undefined;
  const styleBaseline = st.baseline as { have: number; need: number } | undefined;
  const ci = (citations?.evidence ?? {}) as Evidence;
  const refs = (ci.references as Reference[] | undefined) ?? [];
  const missing = refs.filter((r) => r.status === "missing");
  const found = refs.filter((r) => r.status === "found");
  const format = ci.format as CitationFormat | null | undefined;
  const entryIssues = (format?.entries ?? []).filter((e) => e.issues.length > 0);

  return (
    <div className="px-6 py-5 border-b border-ink-700">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-1">{t("Details for each check")}</div>
      <p className="text-xs text-ink-500 mb-2">{t("Signals for a conversation with the student, not proof on their own.")}</p>
      <div className="divide-y divide-[var(--line-strong)]">
        {genre && typeof ge.genre === "string" && (
          <Row tone="muted" title={t("Text type: {label}", { label: currentLang() === "ru" ? String(ge.local_label ?? ge.label) : `${String(ge.label)}${ge.local_label && ge.local_label !== ge.label ? ` (${String(ge.local_label)})` : ""}` })}>
            {((ge.cues as string[] | undefined) ?? []).length > 0 && <>{t("Recognised by:")} <Chips items={(ge.cues as string[]).slice(0, 8).map((c) => t(c))} /></>}
          </Row>
        )}
        {evasion && (
          evasion.verdict === "fake" || evasion.verdict === "suspicious" ? (
            <Row tone="alert" title={t("The text was altered to slip past checkers")}>
              {mixed.length > 0 && <>{t("Words mixing look-alike letters from another alphabet:")} <Chips items={mixed.slice(0, 12)} /></>}
              {invisible.length > 0 && <div className="mt-1">{t("Invisible characters:")} {invisible.map(([k, v]) => `${k} × ${v}`).join(", ")}</div>}
              {hidden.length > 0 && <div className="mt-1">{t("Hidden text in the document:")} {hidden.slice(0, 3).map((h) => `"${h.text}" (${h.reasons.map((r) => t(r)).join(", ")})`).join("; ")}</div>}
            </Row>
          ) : (
            <Row tone="ok" title={t("No character tricks or hidden text")} />
          )
        )}
        {grade && (
          grade.verdict === "suspicious" ? (
            <Row tone="alert" title={t("Language well above {level}", { level })}>
              {beyond.length > 0 && <>{t("Words unusual at this age:")} <Chips items={beyond.slice(0, 14)} /></>}
              {gr.readability_grade != null && <div className="mt-1">{t("Readability is about grade {n}.", { n: String(gr.readability_grade) })}</div>}
            </Row>
          ) : gradeBaseline ? (
            <Row tone="muted" title={gradeBaseline.have < gradeBaseline.need ? t("Above {level}, not enough data to judge yet", { level }) : t("Above {level}, as usual for this student", { level })}>
              {gradeBaseline.have < gradeBaseline.need
                ? t("{have} of {need} earlier works. A strong student is compared with their own level, so this is not flagged until there is enough of their work.", { have: gradeBaseline.have, need: gradeBaseline.need })
                : t("Earlier work from this student is at a similar level, so this is not unusual for them.")}
            </Row>
          ) : gr.reason ? (
            <Row tone="muted" title={t("Age fit not checked")}>{gr.reason === "class level not set" ? t("Set the class year in class settings to compare vocabulary with the students' age.") : t(String(gr.reason))}</Row>
          ) : (
            <Row tone="ok" title={t("Vocabulary fits {level}", { level })} />
          )
        )}
        {style && (
          style.verdict === "suspicious" ? (
            <Row tone="alert" title={t("Style differs sharply from this student's earlier work")}>
              {t("Compared with {n} earlier submissions in this class.", { n: drift?.history_size ?? 0 })}
            </Row>
          ) : drift ? (
            <Row tone="ok" title={t("Consistent with this student's earlier work")}>{t("Compared with {n} earlier submissions.", { n: drift.history_size })}</Row>
          ) : (
            <Row tone="muted" title={t("Not enough data yet for a style comparison: {have} of {need} earlier works", { have: styleBaseline?.have ?? 0, need: styleBaseline?.need ?? 3 })} />
          )
        )}
        {citations && refs.length === 0 && ci.genre === "report" && (
          <Row tone="muted" title={t("A research-style text with no sources at all")} />
        )}
        {citations && refs.length > 0 && (
          citations.verdict === "suspicious" ? (
            <Row tone="alert" title={t("{missing} of {total} cited sources could not be found", { missing: missing.length, total: refs.length })}>
              <MissingList items={missing} />
            </Row>
          ) : missing.length > 0 ? (
            <Row tone="muted" title={t("{found} sources found, {missing} not found", { found: found.length, missing: missing.length })}>
              <MissingList items={missing} />
            </Row>
          ) : found.length > 0 ? (
            <Row tone="ok" title={t("All {n} checked sources exist", { n: found.length })} />
          ) : (
            <Row tone="muted" title={t("Cited sources could not be checked right now")} />
          )
        )}
        {format && (
          format.issue_count > 0 ? (
            <Row tone="muted" title={t("Reference list: {style}, formatting issues: {n}", { style: format.style ? format.label : t("style not recognised"), n: format.issue_count })}>
              {format.issues.length > 0 && (
                <ul className="mt-1 space-y-1">
                  {format.issues.map((i) => <li key={i}>{t(i)}</li>)}
                </ul>
              )}
              {entryIssues.slice(0, 5).map((e) => (
                <div key={e.entry} className="mt-2">
                  <div className="text-ink-200 break-words">{e.entry}</div>
                  <div className="text-ink-500">{e.issues.map((i) => t(i)).join("; ")}</div>
                </div>
              ))}
            </Row>
          ) : (
            <Row tone="ok" title={t("Reference list follows {style}", { style: format.label })} />
          )
        )}
        {shadow && typeof sh.share === "number" && (
          shadow.verdict === "suspicious" ? (
            <Row tone="alert" title={t("Follows an AI answer to the assignment: {n}% of sentences, same order", { n: Math.round(sh.share * 100) })}>
              {shadowPairs.map((p) => (
                <div key={p.student} className="mt-2">
                  <div className="text-ink-200">{p.student}</div>
                  <div className="text-ink-500">{t("AI:")} {p.ai}</div>
                </div>
              ))}
            </Row>
          ) : (
            <Row tone="ok" title={t("Does not follow the {n} AI answers to this class's assignments", { n: String(sh.answers_compared ?? "") })} />
          )
        )}
        {segments.length >= 2 && (
          <Row tone={spread >= SEGMENT_SPREAD_ALERT ? "alert" : "muted"} title={spread >= SEGMENT_SPREAD_ALERT ? t("Some passages read far more machine-like than the rest") : t("Passages read alike")}>
            <div className="mt-1 space-y-1.5">
              {segments.map((s, i) => (
                <div key={i} className="grid grid-cols-[3rem_1fr] gap-2 items-start">
                  <div className="mt-1.5 h-1 bg-[var(--line-strong)] relative">
                    <span className={`absolute inset-y-0 left-0 ${s.ai_probability >= 0.75 ? "bg-signal-blood" : s.ai_probability >= 0.45 ? "bg-signal-amber" : "bg-signal-sage"}`} style={{ width: `${Math.round(s.ai_probability * 100)}%` }} />
                  </div>
                  <div className={s.ai_probability >= 0.75 ? "text-ink-100" : "text-ink-500"}>{s.excerpt}{s.excerpt.length >= 240 ? "..." : ""}</div>
                </div>
              ))}
            </div>
            <div className="mt-1.5 text-ink-600">{t("Per-passage scores are indicative and do not change the verdict.")}</div>
          </Row>
        )}
        {phrases.length >= 3 && (
          <Row tone="muted" title={t("Stock phrases common in chatbot writing")}>
            <Chips items={phrases.slice(0, 10)} />
          </Row>
        )}
      </div>
    </div>
  );
}
