import type { AnalysisResult, Submission } from "../types";
import { currentLang, msg, t } from "../i18n";
import { levelName, readabilitySentence } from "./TeacherSummary";

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
  const segments = (cl.segments as { excerpt: string; text?: string; ai_probability: number }[] | undefined) ?? [];
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
  const punct = Object.entries((ev.lookalike_punctuation as Record<string, number> | undefined) ?? {});
  const marks = typeof ev.stray_marks === "number" ? ev.stray_marks : 0;
  const styled = (ev.styled_letter_words as string[] | undefined) ?? [];
  const beyond = (gr.beyond_level_words as string[] | undefined) ?? [];
  const phrases = Object.keys(((st.phrasebook as Evidence | undefined)?.hits as Record<string, number> | undefined) ?? {});
  const drift = st.drift as { score: number; history_size: number } | undefined;
  const gradeBaseline = gr.baseline as { have: number; need: number } | undefined;
  const styleBaseline = st.baseline as { have: number; need: number } | undefined;
  const styleKind = st.group === "personal" ? t("personal writing") : st.group === "expository" ? t("essays and reports") : "";
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
            <Row tone="alert" title={t("Attempt to hide AI traces: the text was altered to slip past checkers")}>
              {mixed.length > 0 && <>{t("Words mixing look-alike letters from another alphabet:")} <Chips items={mixed.slice(0, 12)} /></>}
              {invisible.length > 0 && <div className="mt-1">{t("Invisible characters:")} {invisible.map(([k, v]) => `${k} × ${v}`).join(", ")}</div>}
              {hidden.length > 0 && <div className="mt-1">{t("Hidden text in the document:")} {hidden.slice(0, 3).map((h) => `"${h.text}" (${h.reasons.map((r) => t(r)).join(", ")})`).join("; ")}</div>}
              {punct.length > 0 && <div className="mt-1">{t("Look-alike punctuation from other alphabets:")} {punct.map(([k, v]) => `${t(k)} × ${v}`).join(", ")}</div>}
              {marks >= 3 && <div className="mt-1">{t("Stray accent marks on ordinary words: {n}", { n: marks })}</div>}
              {styled.length > 0 && <>{t("Words with styled or fullwidth letters:")} <Chips items={styled.slice(0, 12)} /></>}
            </Row>
          ) : (
            <Row tone="ok" title={t("No character tricks or hidden text")} />
          )
        )}
        {grade && (
          grade.verdict === "suspicious" ? (
            <Row tone="alert" title={t("Language well above {level}", { level })}>
              {beyond.length > 0 && <>{t("Words unusual at this age:")} <Chips items={beyond.slice(0, 14)} /></>}
              {typeof gr.readability_grade === "number" && <div className="mt-1">{readabilitySentence(gr.readability_grade, typeof gr.level === "number" ? gr.level : null)}</div>}
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
            <Row tone="muted" title={t("Not enough data yet for a style comparison: {have} of {need} earlier works", { have: styleBaseline?.have ?? 0, need: styleBaseline?.need ?? 3 })}>
              {styleKind && t("Style is only compared with the same kind of text; this one is counted with the student's {kind}.", { kind: styleKind })}
            </Row>
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
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ink-500">
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-signal-blood/40" />{t("reads machine-like (75%+)")}</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-signal-amber/30" />{t("mixed (45-75%)")}</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm border border-white/15" />{t("reads human")}</span>
            </div>
            <div className="mt-3 rounded-xl border border-white/5 bg-ink-950/40 p-3 max-h-[30rem] overflow-y-auto space-y-1.5">
              {segments.map((seg, i) => {
                const pct = Math.round(seg.ai_probability * 100);
                const high = seg.ai_probability >= 0.75;
                const mid = !high && seg.ai_probability >= 0.45;
                const body = seg.text ?? `${seg.excerpt}${seg.excerpt.length >= 240 ? "..." : ""}`;
                return (
                  <p
                    key={i}
                    title={t("{n}% machine-like", { n: pct })}
                    className={`relative rounded-r-lg border-l-2 py-2 pl-3 pr-14 text-[13px] leading-relaxed whitespace-pre-line ${
                      high ? "border-signal-blood/70 bg-signal-blood/10 text-ink-50" : mid ? "border-signal-amber/60 bg-signal-amber/[0.07] text-ink-100" : "border-transparent text-ink-400"
                    }`}
                  >
                    {body}
                    <span className={`absolute right-2.5 top-2 font-mono text-[10px] ${high ? "text-signal-blood" : mid ? "text-signal-amber" : "text-ink-600"}`}>{pct}%</span>
                  </p>
                );
              })}
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
