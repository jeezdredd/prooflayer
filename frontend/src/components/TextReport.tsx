import type { AnalysisResult, Submission } from "../types";
import { currentLang, msg, t, tn } from "../i18n";
import { NOT_COVERED, STYLE_KIND, levelName, promptText, readabilityLines, splitRefs, styleBaselineText, styleChanges } from "./TeacherSummary";

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

type Marker = (cluster: string, word: string) => string | null;

function clusters(word: string): string[] {
  const out: string[] = [];
  for (const ch of word) {
    if (out.length > 0 && /\p{M}/u.test(ch)) out[out.length - 1] += ch;
    else out.push(ch);
  }
  return out;
}

function Chips({ items, mark }: { items: string[]; mark?: Marker }) {
  return (
    <span className="flex flex-wrap gap-1.5 mt-1.5">
      {items.map((w) => (
        <span key={w} className="font-mono text-[11px] px-1.5 py-0.5 border border-[var(--line-strong)] text-ink-200">
          {mark ? clusters(w).map((c, i) => {
            const why = mark(c, w);
            return why ? <mark key={i} title={why} className="bg-signal-amber/30 text-ink-50 rounded-sm">{c}</mark> : c;
          }) : w}
        </span>
      ))}
    </span>
  );
}

function Lines({ items }: { items: string[] }) {
  return (
    <>
      {items.map((line) => <div key={line} className="mt-1">{line}</div>)}
    </>
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
const CYRILLIC = /[\u0400-\u04ff]/;
const LATIN = /[a-z\u00c0-\u024f]/i;
const GREEK = /[\u0370-\u03ff]/;
const SHOWN_MARK = "\u00b7";
const LOOKALIKE_PUNCT = "\u2024\ufe52\uff0e\u0589\u06d4\ua4f8\ua4f9\ufe50\uff0c\u060c\uff1a\uff1b\uff01\uff1f";
const COMMON_MARKS = "\u0300\u0301\u0302\u0303\u0304\u0306\u0307\u0308\u030a\u030b\u030c\u0327\u0328";

const KIND_LABEL: Record<string, string> = {
  doi: "DOI",
  arxiv: "arXiv",
  isbn: "ISBN",
  url: msg("Link"),
  bibliography: msg("Reference"),
  quote: msg("Quote"),
};

function script(ch: string): "cyrillic" | "latin" | "greek" | null {
  if (CYRILLIC.test(ch)) return "cyrillic";
  if (LATIN.test(ch)) return "latin";
  if (GREEK.test(ch)) return "greek";
  return null;
}

function majorScript(word: string): string | null {
  const counts: Record<string, number> = {};
  for (const ch of word) {
    const s = script(ch);
    if (s) counts[s] = (counts[s] ?? 0) + 1;
  }
  const ranked = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  return ranked[0]?.[0] ?? null;
}

const markForeign: Marker = (cluster, word) => {
  const s = script(cluster);
  if (!s || s === majorScript(word)) return null;
  return s === "latin" ? t("Latin letter") : s === "greek" ? t("Greek letter") : t("Russian letter");
};

const markHidden: Marker = (cluster) => (cluster === SHOWN_MARK ? t("hidden character here") : null);
const markPunct: Marker = (cluster) => (LOOKALIKE_PUNCT.includes(cluster) ? t("punctuation mark from another alphabet") : null);
const markAccent: Marker = (cluster) =>
  [...cluster.normalize("NFD")].some((ch) => /\p{M}/u.test(ch) && !COMMON_MARKS.includes(ch)) ? t("stray mark") : null;

function RefList({ items }: { items: Reference[] }) {
  return (
    <ul className="mt-1 space-y-1">
      {items.slice(0, 8).map((r) => (
        <li key={`${r.kind}:${r.value}`} className="break-words">
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500 mr-2">{KIND_LABEL[r.kind] ? t(KIND_LABEL[r.kind]) : r.kind}</span>
          <span className="text-ink-200">{r.value}</span>
          {r.detail && !NOT_COVERED.includes(r.detail) && (
            /^https?:\/\//.test(r.detail) ? (
              <span className="text-ink-500"> (<a href={r.detail} target="_blank" rel="noopener noreferrer nofollow" className="underline hover:text-signal-amber break-all">{t("found here")}</a>)</span>
            ) : (
              <span className="text-ink-500"> ({r.status === "found" && r.kind === "bibliography" ? t("found: {title}", { title: r.detail }) : t(r.detail)})</span>
            )
          )}
        </li>
      ))}
    </ul>
  );
}

function genreLabel(ge: Evidence): string {
  if (currentLang() === "ru") return ge.language === "ru" && ge.local_label ? String(ge.local_label) : t(String(ge.label));
  return `${String(ge.label)}${ge.local_label && ge.local_label !== ge.label ? ` (${String(ge.local_label)})` : ""}`;
}

function rareWordsLabel(level: number | null): string {
  return level !== null && level <= 11 ? t("Bookish and scientific words, rare at this age:") : t("Rare words:");
}

export default function TextReport({ submission, student = false }: { submission: Submission; student?: boolean }) {
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

  const levelNum = typeof gr.level === "number" ? gr.level : null;
  const level = levelNum !== null ? levelName(levelNum) : null;
  const ev = (evasion?.evidence ?? {}) as Evidence;
  const st = (style?.evidence ?? {}) as Evidence;
  const mixed = (ev.mixed_script_words as string[] | undefined) ?? [];
  const mixedCount = typeof ev.mixed_script_count === "number" ? ev.mixed_script_count : mixed.length;
  const mostlyCyrillic = mixed.filter((w) => majorScript(w) === "cyrillic").length > mixed.length / 2;
  const invisible = Object.entries((ev.invisible_characters as Record<string, number> | undefined) ?? {});
  const hidden = (ev.hidden_runs as { text: string; reasons: string[] }[] | undefined) ?? [];
  const punct = Object.entries((ev.lookalike_punctuation as Record<string, number> | undefined) ?? {});
  const marks = typeof ev.stray_marks === "number" ? ev.stray_marks : 0;
  const oddSpaces = typeof ev.odd_spaces === "number" ? ev.odd_spaces : 0;
  const tags = typeof ev.tag_characters === "number" ? ev.tag_characters : 0;
  const styled = (ev.styled_letter_words as string[] | undefined) ?? [];
  const examples = (key: string) => (ev[key] as string[] | undefined) ?? [];
  const beyond = (gr.beyond_level_words as string[] | undefined) ?? [];
  const facts = readabilityLines(gr);
  const plainFacts = readabilityLines(gr, false);
  const phrases = Object.keys(((st.phrasebook as Evidence | undefined)?.hits as Record<string, number> | undefined) ?? {}).map((p) => p.replace(/[,\s]+$/, ""));
  const drift = st.drift as { score: number; history_size: number } | undefined;
  const changes = styleChanges(st);
  const gradeBaseline = gr.baseline as { have: number; need: number } | undefined;
  const styleBaseline = st.baseline as { have: number; need: number } | undefined;
  const styleExplained = styleBaselineText(st);
  const styleKind = typeof st.group === "string" && STYLE_KIND[st.group] ? t(STYLE_KIND[st.group]) : "";
  const ci = (citations?.evidence ?? {}) as Evidence;
  const { sources, quotes } = splitRefs(ci);
  const refs = sources as Reference[];
  const missing = refs.filter((r) => r.status === "missing");
  const found = refs.filter((r) => r.status === "found");
  const unchecked = refs.filter((r) => r.status === "unchecked");
  const notCovered = unchecked.filter((r) => NOT_COVERED.includes(r.detail));
  const quotesFound = quotes.filter((r) => r.status === "found").length;
  const format = ci.format as CitationFormat | null | undefined;
  const entryIssues = (format?.entries ?? []).filter((e) => e.issues.length > 0);
  const prompt = promptText(sh.prompt);
  const rareChips = beyond.length > 0 && <div className="mt-1">{rareWordsLabel(levelNum)} <Chips items={beyond.slice(0, 14)} /></div>;

  return (
    <div className="px-6 py-5 border-b border-ink-700">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-1">{t("Details for each check")}</div>
      {!student && <p className="text-xs text-ink-500 mb-2">{t("Signals for a conversation with the student, not proof on their own.")}</p>}
      <div className="divide-y divide-[var(--line-strong)]">
        {genre && typeof ge.genre === "string" && ge.genre !== "other" && (
          <Row tone="muted" title={t("Text type: {label}", { label: genreLabel(ge) })}>
            {((ge.cues as string[] | undefined) ?? []).length > 0 && <>{t("Recognised by:")} <Chips items={(ge.cues as string[]).slice(0, 8).map((c) => t(c))} /></>}
          </Row>
        )}
        {evasion && evasion.verdict === "error" && <Row tone="muted" title={t("The hidden tricks check did not run")} />}
        {evasion && evasion.verdict !== "error" && (
          evasion.verdict === "fake" || evasion.verdict === "suspicious" ? (
            <Row tone="alert" title={t("Attempt to hide AI traces: the text was altered to slip past checkers")}>
              {mixed.length > 0 && (
                <div className="mt-1">
                  {mostlyCyrillic
                    ? tn(mixedCount, "In {n} word Russian letters were replaced with look-alike Latin ones, for example:", "In {n} words Russian letters were replaced with look-alike Latin ones, for example:")
                    : tn(mixedCount, "In {n} word letters were replaced with look-alike ones from another alphabet, for example:", "In {n} words letters were replaced with look-alike ones from another alphabet, for example:")}
                  <Chips items={mixed.slice(0, 12)} mark={markForeign} />
                </div>
              )}
              {invisible.length > 0 && (
                <div className="mt-1">
                  {t("Invisible characters:")} {invisible.map(([k, v]) => `${t(k)} × ${v}`).join(", ")}
                  {examples("invisible_words").length > 0 && <Chips items={examples("invisible_words")} mark={markHidden} />}
                </div>
              )}
              {hidden.length > 0 && <div className="mt-1">{t("Hidden text in the document:")} {hidden.slice(0, 3).map((h) => `"${h.text}" (${h.reasons.map((r) => t(r)).join(", ")})`).join("; ")}</div>}
              {punct.length > 0 && (
                <div className="mt-1">
                  {t("Look-alike punctuation from other alphabets:")} {punct.map(([k, v]) => `${t(k)} × ${v}`).join(", ")}
                  {examples("punct_words").length > 0 && <Chips items={examples("punct_words")} mark={markPunct} />}
                </div>
              )}
              {marks >= 3 && (
                <div className="mt-1">
                  {t("Stray accent marks on ordinary words: {n}", { n: marks })}
                  {examples("stray_mark_words").length > 0 && <Chips items={examples("stray_mark_words")} mark={markAccent} />}
                </div>
              )}
              {oddSpaces >= 10 && (
                <div className="mt-1">
                  {t("Unusual spaces between words: {n}", { n: oddSpaces })}
                  {examples("odd_space_words").length > 0 && <Chips items={examples("odd_space_words")} mark={markHidden} />}
                </div>
              )}
              {tags > 0 && (
                <div className="mt-1">
                  {t("Hidden tag characters: {n}", { n: tags })}
                  {examples("tag_words").length > 0 && <Chips items={examples("tag_words")} mark={markHidden} />}
                </div>
              )}
              {styled.length > 0 && <div className="mt-1">{t("Words with styled or fullwidth letters:")} <Chips items={styled.slice(0, 12)} /></div>}
            </Row>
          ) : (
            <Row tone="ok" title={t("No character tricks or hidden text")} />
          )
        )}
        {grade && grade.verdict === "error" && <Row tone="muted" title={t("The age fit check did not run")} />}
        {grade && grade.verdict !== "error" && (
          grade.verdict === "suspicious" ? (
            <Row tone="alert" title={level ? t("Language well above {level}", { level }) : t("Language well above the student's age")}>
              {rareChips}
              <Lines items={facts} />
            </Row>
          ) : gradeBaseline ? (
            <Row
              tone="muted"
              title={
                gradeBaseline.have < gradeBaseline.need
                  ? level ? t("Above {level}, not enough data to judge yet", { level }) : t("Above the student's age, not enough data to judge yet")
                  : level ? t("Above {level}, as usual for this student", { level }) : t("Above the student's age, as usual for this student")
              }
            >
              {gradeBaseline.have < gradeBaseline.need
                ? t("{have} of {need} earlier works. A strong student is compared with their own level, so this is not flagged until there is enough of their work.", { have: gradeBaseline.have, need: gradeBaseline.need })
                : t("Earlier work from this student is at a similar level, so this is not unusual for them.")}
              {rareChips}
              <Lines items={facts} />
            </Row>
          ) : gr.reason ? (
            gr.reason === "class level not set" ? (
              !student && <Row tone="muted" title={t("Age fit not checked")}>{t("Set the class year in class settings to compare vocabulary with the students' age.")}</Row>
            ) : (
              <Row tone="muted" title={t("Age fit not checked")}>{gr.reason === "text too short" ? t("Too short to judge the vocabulary") : t(String(gr.reason))}</Row>
            )
          ) : beyond.length >= 2 ? (
            <Row tone="ok" title={level ? t("Vocabulary mostly fits {level}", { level }) : t("Vocabulary mostly fits the age")}>
              {rareChips}
              {!student && <div className="mt-1">{t("If in doubt, ask the student to explain these words.")}</div>}
              <Lines items={plainFacts} />
            </Row>
          ) : (
            <Row tone="ok" title={level ? t("Vocabulary fits {level}", { level }) : t("Vocabulary fits the student's age")}>
              <Lines items={plainFacts} />
            </Row>
          )
        )}
        {style && style.verdict === "error" && <Row tone="muted" title={t("The style check did not run")} />}
        {style && style.verdict !== "error" && (
          st.reason === "text too short" ? (
            <Row tone="muted" title={t("Too short to compare style (needs {n} words or more)", { n: typeof st.min_words === "number" ? st.min_words : 60 })} />
          ) : style.verdict === "suspicious" ? (
            <Row tone="alert" title={t("Style differs sharply from this student's earlier work")}>
              {changes.length > 0 ? <Lines items={changes} /> : <div className="mt-1">{t("The small words the student usually uses (prepositions, conjunctions) changed.")}</div>}
              <div className="mt-1">{t("Compared with {n} earlier submissions in this class.", { n: drift?.history_size ?? 0 })}</div>
            </Row>
          ) : drift ? (
            <Row tone="ok" title={t("Consistent with this student's earlier work")}>{t("Compared with {n} earlier submissions.", { n: drift.history_size })}</Row>
          ) : styleExplained ? (
            <Row tone="muted" title={t("Nothing to compare with yet")}>{styleExplained}</Row>
          ) : (
            <Row tone="muted" title={t("Not enough data yet for a style comparison: {have} of {need} earlier works", { have: styleBaseline?.have ?? 0, need: styleBaseline?.need ?? 3 })}>
              {styleKind && t("Style is only compared with the same kind of text ({kind}).", { kind: styleKind })}
            </Row>
          )
        )}
        {citations && refs.length === 0 && ci.sources_expected === true && (
          <Row tone="muted" title={t("A research-style text with no sources at all")} />
        )}
        {citations && refs.length > 0 && (
          citations.verdict === "suspicious" && missing.length > 0 ? (
            <Row tone="alert" title={t("{missing} of {total} cited sources could not be found", { missing: missing.length, total: refs.length })}>
              <RefList items={missing} />
              {found.length > 0 && <div className="mt-2">{t("Found:")} <RefList items={found} /></div>}
            </Row>
          ) : missing.length > 0 ? (
            <Row tone="muted" title={t("{found} sources found, {missing} not found", { found: found.length, missing: missing.length })}>
              <RefList items={missing} />
              {found.length > 0 && <div className="mt-2">{t("Found:")} <RefList items={found} /></div>}
            </Row>
          ) : found.length > 0 ? (
            <Row tone="ok" title={found.length === refs.length ? t("All {n} checked sources exist", { n: found.length }) : t("{found} of {total} sources found", { found: found.length, total: refs.length })}>
              <RefList items={found} />
              {notCovered.length > 0 && <div className="mt-2">{t("Russian books are not in open catalogues, check them by hand:")} <RefList items={notCovered} /></div>}
            </Row>
          ) : notCovered.length > 0 ? (
            <Row tone="muted" title={t("Russian books are not in open catalogues, check them by hand:")}>
              <RefList items={unchecked} />
            </Row>
          ) : (
            <Row tone="muted" title={t("Cited sources could not be checked right now")}>
              <RefList items={unchecked} />
            </Row>
          )
        )}
        {citations && quotes.length > 0 && (
          <Row tone="muted" title={t("Quotes found on the web: {found} of {total}", { found: quotesFound, total: quotes.length })}>
            {quotesFound < quotes.length && t("A quote that was not found online is not necessarily invented: many books are not online.")}
          </Row>
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
            student ? (
              <Row tone="alert" title={t("Much of the text repeats an AI answer to the assignment")} />
            ) : (
              <Row tone="alert" title={t("Follows an AI answer to the assignment: {n}% of sentences, same order", { n: Math.round(sh.share * 100) })}>
                {prompt && <div className="mt-1">{t("Assignment: «{prompt}»", { prompt })}</div>}
                {shadowPairs.map((p) => (
                  <div key={p.student} className="mt-2">
                    <div className="text-ink-200">{t("In the work:")} {p.student}</div>
                    <div className="text-ink-500">{t("In the AI answer:")} {p.ai}</div>
                  </div>
                ))}
              </Row>
            )
          ) : (
            <Row
              tone="ok"
              title={prompt ? t("Does not follow the AI answers to «{prompt}»", { prompt }) : t("Does not follow the {n} AI answers to this class's assignments", { n: String(sh.answers_compared ?? "") })}
            />
          )
        )}
        {!student && shadow && sh.reason === "AI answers were created after this work was handed in" && (
          <Row tone="muted" title={t("AI answers were made after this work was handed in")}>{t("Only work handed in after the AI answers were made is compared with them.")}</Row>
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
                  <div
                    key={i}
                    className={`rounded-r-lg border-l-2 py-2 pl-3 pr-3 text-[13px] leading-relaxed ${
                      high ? "border-signal-blood/70 bg-signal-blood/10 text-ink-50" : mid ? "border-signal-amber/60 bg-signal-amber/[0.07] text-ink-100" : "border-transparent text-ink-400"
                    }`}
                  >
                    <span className={`block font-mono text-[10px] mb-1 ${high ? "text-signal-blood" : mid ? "text-signal-amber" : "text-ink-600"}`}>{t("{n}% like AI writing", { n: pct })}</span>
                    <p className="whitespace-pre-line">{body}</p>
                  </div>
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
