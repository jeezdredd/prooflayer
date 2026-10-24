import clsx from "clsx";
import type { AnalysisResult, OriginalityMatch, OriginalityReport, Submission } from "../types";
import { locale, msg, t, tn } from "../i18n";

type Evidence = Record<string, unknown>;
export type CheckStatus = "ok" | "look" | "alert" | "wait" | "off";

export interface Check {
  key: string;
  title: string;
  status: CheckStatus;
  headline: string;
  detail?: string;
  next?: string;
}

const TEXT_ANALYZERS = ["text_classifier", "text_evasion", "text_grade_fit", "text_style", "text_citations", "text_shadow"];
const MEDIA_DETECTORS = ["community_forensics", "ai_detector", "custom_detector", "clip_probe", "llm_vision", "audio_spectrogram", "video_frame"];
const FLAGGED = new Set(["fake", "likely_fake", "suspicious"]);
const VOTED = new Set(["fake", "likely_fake", "suspicious", "authentic", "authentic_edited"]);
const AI_LOOK = 0.45;
const SPREAD_ALERT = 0.5;
const PROMPT_CHARS = 90;
const SAMPLE_WORDS = 5;
const MOSTLY_FITS_WORDS = 2;
export const NOT_COVERED = ["not covered by open catalogues", "not in OpenAlex, Crossref or web search, which cover few Russian-language books"];

const STATUS_STYLE: Record<CheckStatus, { word: string; tile: string; chip: string; dot: string; bar: string; text: string }> = {
  ok: { word: msg("Clear"), tile: "border-signal-sage/40", chip: "bg-signal-sage/15 text-signal-sage", dot: "bg-signal-sage", bar: "border-signal-sage", text: "text-signal-sage" },
  look: { word: msg("Look closer"), tile: "border-signal-amber/50 bg-signal-amber/5", chip: "bg-signal-amber/15 text-signal-amber", dot: "bg-signal-amber", bar: "border-signal-amber", text: "text-signal-amber" },
  alert: { word: msg("Flag"), tile: "border-signal-blood/60 bg-signal-blood/5", chip: "bg-signal-blood/15 text-signal-blood", dot: "bg-signal-blood", bar: "border-signal-blood", text: "text-signal-blood" },
  wait: { word: msg("Needs more work"), tile: "border-[var(--line-strong)]", chip: "bg-ink-800 text-ink-300", dot: "bg-ink-500", bar: "border-ink-500", text: "text-ink-300" },
  off: { word: msg("Not checked"), tile: "border-[var(--line-strong)] opacity-70", chip: "bg-ink-800 text-ink-500", dot: "bg-ink-600", bar: "border-ink-600", text: "text-ink-400" },
};

const GENERIC_NEXT = msg("Next step: ask the student to talk you through how they wrote it, or to explain a passage in their own words. A flag is a reason to ask, not proof.");

function byName(submission: Submission, name: string): AnalysisResult | undefined {
  return submission.analysis_results?.find((r) => r.analyzer_name === name);
}

function evidence(result: AnalysisResult | undefined): Evidence {
  return (result?.evidence ?? {}) as Evidence;
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function words(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((w): w is string => typeof w === "string") : [];
}

export function fmtNum(value: number): string {
  return value.toLocaleString(locale(), { maximumFractionDigits: 1 });
}

export function isTextSubmission(submission: Submission): boolean {
  return TEXT_ANALYZERS.some((name) => byName(submission, name));
}

function broken(key: string, title: string, student: boolean, submission: Submission): Check {
  const stale = !!submission.ensemble && !submission.ensemble.is_current;
  return {
    key,
    title,
    status: "off",
    headline: t("This check did not run"),
    detail: student ? undefined : stale ? t("Press «Re-analyze» at the top of the page to run it again.") : t("Upload the work again later to repeat the check."),
  };
}

function aiCheck(submission: Submission, student: boolean): Check | null {
  const result = byName(submission, "text_classifier");
  if (!result) return null;
  const title = t("AI writing");
  if (result.verdict === "error") return broken("ai", title, student, submission);
  const ev = evidence(result);
  const p = num(ev.ai_probability);
  if (p === null) {
    if (ev.reason === "text too short for a verdict") return { key: "ai", title, status: "off", headline: t("Too short to judge (needs about 90 words)") };
    if (ev.reason === "language not calibrated") return { key: "ai", title, status: "off", headline: t("This check cannot read texts in this language yet") };
    if (ev.reason === "text is empty") return { key: "ai", title, status: "off", headline: t("No text found in the file") };
    return { key: "ai", title, status: "off", headline: t("Could not score this text") };
  }
  const score = Math.round(p * 100);
  const uneven = num(ev.segment_spread) !== null && (ev.segment_spread as number) >= SPREAD_ALERT;
  const unevenNote = uneven ? ` ${t("Some passages read far more machine-like than the rest.")}` : "";
  const classifierScore = num(ev.classifier_score);
  const threshold = num(ev.threshold);
  const overLine =
    result.verdict === "fake" ||
    ev.over_flag_line === true ||
    (ev.over_flag_line === undefined && classifierScore !== null && threshold !== null && classifierScore >= threshold);
  if (overLine) {
    return {
      key: "ai",
      title,
      status: "alert",
      headline: t("Reads like chatbot writing"),
      detail: t("Scored {n} out of 100 towards machine writing, above the flag line that only about 1 in 100 texts written by people cross.", { n: score }) + unevenNote,
    };
  }
  const leaning = FLAGGED.has(result.verdict) || p >= AI_LOOK;
  if (leaning || uneven) {
    return {
      key: "ai",
      title,
      status: "look",
      headline: uneven ? t("Parts may be machine-written") : t("Some machine-like writing"),
      detail: (leaning
        ? t("Scored {n} out of 100 towards machine writing. That is more than most texts written by people, but below the line where we raise a flag.", { n: score })
        : t("Scored {n} out of 100 towards machine writing.", { n: score })) + unevenNote,
    };
  }
  return { key: "ai", title, status: "ok", headline: t("Reads like a person's writing"), detail: t("Scored {n} out of 100 towards machine writing.", { n: score }) };
}

export function webScope(report: OriginalityReport): string {
  const status = report.web_status ?? (report.web_searched ? "ok" : "off");
  if (status === "ok") return t("Compared with students' work in ProofLayer, Wikipedia and a web search.");
  if (status === "failed") return t("The web search did not answer this time, so only students' work in ProofLayer was compared.");
  if (status === "short") return t("Too short for a web search; compared with students' work in ProofLayer.");
  return t("Compared with students' work in ProofLayer; web search is off for this school.");
}

export function isHiddenSource(match: OriginalityMatch): boolean {
  if (match.source === "web") return false;
  return !!match.hidden || !match.submission_id;
}

function sourceName(match: OriginalityMatch): string {
  if (match.source === "web") {
    if (match.url) {
      try {
        const host = new URL(match.url).hostname.replace(/^www\./, "");
        return match.title ? `${match.title} (${host})` : host;
      } catch {
        return match.title || match.url;
      }
    }
    return match.title || t("a web page");
  }
  if (!isHiddenSource(match) && match.author) return t("work by {name}", { name: match.author });
  return t("another student's work");
}

function copyHeadline(report: OriginalityReport, matched: number): string {
  const web = report.matches.filter((m) => m.source === "web");
  const internal = report.matches.filter((m) => m.source !== "web");
  if (internal.length === 0) return t("{n}% of the text was found on the web", { n: matched });
  if (web.length > 0) return t("{n}% of the text was found on the web and in other students' work", { n: matched });
  const sources = new Set(internal.map((m) => m.submission_id ?? m.submitted_at ?? m.title ?? ""));
  if (sources.size > 1) return t("{n}% of the text matches other students' work", { n: matched });
  const top = internal[0];
  if (!isHiddenSource(top) && top.author) return t("{n}% of the text matches another student's work ({name})", { n: matched, name: top.author });
  return t("{n}% of the text matches another student's work", { n: matched });
}

function copyCheck(submission: Submission): Check | null {
  const report = submission.originality;
  if (!report) return null;
  const title = t("Copying");
  if (report.status === "failed") return { key: "copy", title, status: "off", headline: t("Copy check failed") };
  if (report.status !== "done" || report.originality == null) return { key: "copy", title, status: "wait", headline: t("Still comparing with other work") };
  const scope = webScope(report);
  const matched = 100 - Math.round(report.originality);
  if (report.matches.length === 0) return { key: "copy", title, status: "ok", headline: t("No copied passages found"), detail: scope };
  if (matched < 1) return { key: "copy", title, status: "ok", headline: t("Less than 1% of the text matches other sources"), detail: scope };
  const status: CheckStatus = report.originality >= 85 ? "ok" : report.originality >= 60 ? "look" : "alert";
  const top = report.matches[0];
  return {
    key: "copy",
    title,
    status,
    headline: copyHeadline(report, matched),
    detail: `${t("Main source: {source}.", { source: sourceName(top) })} ${tn(report.matches.length, "Found in {n} source.", "Found in {n} sources.")} ${t("The copied passages are shown below under Originality. Quotes with references are fine.")}`,
    next: t("Next step: compare the matching passages with the source below. If the work does not name that source, the passages were copied."),
  };
}

function trickParts(ev: Evidence): string[] {
  const parts: string[] = [];
  const mixed = num(ev.mixed_script_count) ?? words(ev.mixed_script_words).length;
  if (mixed > 0) parts.push(tn(mixed, "{n} word with swapped letters", "{n} words with swapped letters"));
  const invisible = Object.values((ev.invisible_characters as Record<string, number> | undefined) ?? {}).reduce((a, b) => a + b, 0);
  if (invisible > 0) parts.push(tn(invisible, "{n} invisible character", "{n} invisible characters"));
  if (Array.isArray(ev.hidden_runs) && ev.hidden_runs.length > 0) parts.push(t("hidden text in the file"));
  const punct = Object.values((ev.lookalike_punctuation as Record<string, number> | undefined) ?? {}).reduce((a, b) => a + b, 0);
  if (punct > 0) parts.push(tn(punct, "{n} punctuation mark from another alphabet", "{n} punctuation marks from other alphabets"));
  const marks = num(ev.stray_marks) ?? 0;
  if (marks >= 3) parts.push(tn(marks, "{n} stray mark over letters", "{n} stray marks over letters"));
  const styled = words(ev.styled_letter_words).length;
  if (styled > 0) parts.push(tn(styled, "{n} word in decorative letters", "{n} words in decorative letters"));
  const odd = num(ev.odd_spaces) ?? 0;
  if (odd >= 10) parts.push(tn(odd, "{n} unusual space", "{n} unusual spaces"));
  const tags = num(ev.tag_characters) ?? 0;
  if (tags > 0) parts.push(tn(tags, "{n} hidden tag character", "{n} hidden tag characters"));
  return parts;
}

function trickCheck(submission: Submission, student: boolean): Check | null {
  const result = byName(submission, "text_evasion");
  if (!result) return null;
  const title = t("Hidden tricks");
  if (result.verdict === "error") return broken("tricks", title, student, submission);
  if (result.verdict === "fake" || result.verdict === "suspicious") {
    const ev = evidence(result);
    const parts = trickParts(ev);
    const hidden = Array.isArray(ev.hidden_runs) && ev.hidden_runs.length > 0;
    return {
      key: "tricks",
      title,
      status: "alert",
      headline: t("Attempt to hide AI traces"),
      detail: `${parts.length > 0 ? t("Found: {list}.", { list: parts.join(", ") }) : ""} ${t("This is how text is hidden from AI checks.")}`.trim(),
      next: hidden
        ? t("Next step: open the file, select everything (Ctrl+A) and set the text colour to black: the hidden words will show up.")
        : t("Next step: ask the student how they prepared the text. Swapped letters and invisible characters do not appear by themselves; programs that hide text from AI checks put them there."),
    };
  }
  return { key: "tricks", title, status: "ok", headline: t("No disguised letters or hidden text") };
}

export function levelName(level: number): string {
  return level <= 11 ? t("grade {n}", { n: level }) : t("university year {n}", { n: level - 11 });
}

export const BAND_TEXT: Record<string, string> = {
  primary: msg("primary school"),
  middle: msg("grades 5-9"),
  senior: msg("grades 10-11"),
  university: msg("university"),
  plain: msg("a simple school text"),
  textbook: msg("a textbook"),
  adult: msg("an academic article"),
};

export function readabilityLines(ev: Evidence, interpret = true): string[] {
  const wps = num(ev.words_per_sentence);
  const spw = num(ev.syllables_per_word);
  if (wps === null || spw === null) return [];
  const usual = (ev.usual as Evidence | undefined) ?? {};
  const uwps = num(usual.words_per_sentence);
  const uspw = num(usual.syllables_per_word);
  if (uwps !== null && uspw !== null) {
    return [
      t("Words per sentence: {now} on average, {usual} in this student's earlier work.", { now: fmtNum(wps), usual: fmtNum(uwps) }),
      t("Syllables per word: {now} on average, {usual} in earlier work.", { now: fmtNum(spw), usual: fmtNum(uspw) }),
    ];
  }
  const lines = [t("Words per sentence: {wps} on average. Syllables per word: {spw}.", { wps: fmtNum(wps), spw: fmtNum(spw) })];
  if (!interpret) return lines;
  const level = num(ev.level);
  if (ev.readability_band === "plain") lines.push(t("Short sentences and simple words: an ordinary school text."));
  if (ev.readability_band === "textbook") lines.push(t("Long sentences, as in a textbook. Normal for an argumentative essay."));
  if (ev.readability_band === "adult") {
    lines.push(
      level !== null && level <= 11
        ? t("Very long sentences and bookish words, as in an academic article for adults. Unusual for {level}.", { level: levelName(level) })
        : t("Very long sentences and bookish words, as in an academic article."),
    );
  }
  return lines;
}

function wordSample(ev: Evidence): string {
  return words(ev.beyond_level_words).slice(0, SAMPLE_WORDS).join(", ");
}

function ageCheck(submission: Submission, student: boolean): Check | null {
  const result = byName(submission, "text_grade_fit");
  if (!result) return null;
  const title = t("Age fit");
  if (result.verdict === "error") return broken("age", title, student, submission);
  const ev = evidence(result);
  const levelNum = num(ev.level);
  const level = levelNum !== null ? levelName(levelNum) : null;
  const sample = wordSample(ev);
  const rare = sample ? t("Bookish words, rare at this age: {words}.", { words: sample }) : "";
  const baseline = ev.baseline as { have: number; need: number } | undefined;
  if (ev.reason === "class level not set") {
    if (student) return null;
    return { key: "age", title, status: "off", headline: t("Class year not set"), detail: t("Set the class year in class settings to compare vocabulary with the students' age.") };
  }
  if (ev.reason === "text too short") return { key: "age", title, status: "off", headline: t("Too short to judge the vocabulary") };
  if (ev.reason === "language not supported") return { key: "age", title, status: "off", headline: t("This check cannot read texts in this language yet") };
  if (typeof ev.reason === "string") return { key: "age", title, status: "off", headline: t(ev.reason) };
  if (result.verdict === "suspicious") {
    return {
      key: "age",
      title,
      status: "look",
      headline: level ? t("Vocabulary well above {level}", { level }) : t("Vocabulary well above the student's age"),
      detail: `${rare} ${student ? t("Your earlier work was simpler.") : t("The student's earlier work was simpler.")}`.trim(),
    };
  }
  if (baseline && baseline.have < baseline.need) {
    return {
      key: "age",
      title,
      status: "wait",
      headline: level ? t("Above {level}, too early to judge", { level }) : t("Above the student's age, too early to judge"),
      detail: `${rare} ${t("Strong students are compared with their own level. {have} of {need} earlier works so far.", { have: baseline.have, need: baseline.need })}`.trim(),
    };
  }
  if (baseline) {
    return {
      key: "age",
      title,
      status: "ok",
      headline: level ? t("Above {level}, usual for this student", { level }) : t("Above the student's age, usual for this student"),
      detail: rare || undefined,
    };
  }
  if (words(ev.beyond_level_words).length >= MOSTLY_FITS_WORDS) {
    return {
      key: "age",
      title,
      status: "ok",
      headline: t("Vocabulary mostly fits the age"),
      detail: `${level ? t("Rare words for {level}: {words}.", { level, words: sample }) : t("Rare words for this age: {words}.", { words: sample })}${student ? "" : ` ${t("If in doubt, ask the student to explain these words.")}`}`,
    };
  }
  return { key: "age", title, status: "ok", headline: level ? t("Vocabulary fits {level}", { level }) : t("Vocabulary fits the student's age") };
}

export const STYLE_KIND: Record<string, string> = {
  personal: msg("stories, descriptions, letters"),
  expository: msg("essays, analyses, reports"),
  poem: msg("poems"),
};

export function styleChange(change: { key: string; now: number; usual: number }): string | null {
  const pct = (v: number) => fmtNum(v * 100);
  if (change.key === "sentence_mean") return t("Sentences now average {now} words, earlier {usual}.", { now: fmtNum(change.now), usual: fmtNum(change.usual) });
  if (change.key === "word_length") return t("Words now average {now} letters, earlier {usual}.", { now: fmtNum(change.now), usual: fmtNum(change.usual) });
  if (change.key === "comma") return t("Commas per 100 words: {now} now, {usual} earlier.", { now: pct(change.now), usual: pct(change.usual) });
  if (change.key === "semicolon") return t("Semicolons per 100 words: {now} now, {usual} earlier.", { now: pct(change.now), usual: pct(change.usual) });
  if (change.key === "dash") return t("Dashes per 100 words: {now} now, {usual} earlier.", { now: pct(change.now), usual: pct(change.usual) });
  if (change.key === "rare_share") return t("Rare words: {now}% of the text now, {usual}% earlier.", { now: pct(change.now), usual: pct(change.usual) });
  return null;
}

export function styleChanges(ev: Evidence): string[] {
  const drift = ev.drift as { changes?: { key: string; now: number; usual: number }[] } | undefined;
  return (drift?.changes ?? []).map(styleChange).filter((s): s is string => !!s);
}

export function styleBaselineText(ev: Evidence): string | null {
  const baseline = ev.baseline as { have: number; need: number; total?: number } | undefined;
  if (!baseline || typeof baseline.total !== "number" || baseline.total <= baseline.have) return null;
  const vars = { have: baseline.have, total: baseline.total, need: baseline.need };
  if (typeof ev.group === "string" && STYLE_KIND[ev.group]) {
    return t("{have} of {total} earlier works fit: style is only compared with works of the same kind ({kind}) of 60 words or more. {need} are needed.", {
      ...vars,
      kind: t(STYLE_KIND[ev.group]),
    });
  }
  return t("{have} of {total} earlier works fit: style is only compared with works of the same kind of 60 words or more. {need} are needed.", vars);
}

function styleCheck(submission: Submission, student: boolean): Check | null {
  const result = byName(submission, "text_style");
  if (!result) return null;
  const title = t("Own style");
  if (result.verdict === "error") return broken("style", title, student, submission);
  const ev = evidence(result);
  if (ev.reason === "text too short") return { key: "style", title, status: "off", headline: t("Too short to compare style (needs {n} words or more)", { n: num(ev.min_words) ?? 60 }) };
  if (ev.reason === "language not supported") return { key: "style", title, status: "off", headline: t("This check cannot read texts in this language yet") };
  const drift = ev.drift as { history_size: number } | undefined;
  const baseline = ev.baseline as { have: number; need: number } | undefined;
  if (result.verdict === "suspicious") {
    const changes = styleChanges(ev);
    const count = tn(drift?.history_size ?? 0, "Compared with {n} earlier work in this class.", "Compared with {n} earlier works in this class.");
    return {
      key: "style",
      title,
      status: "look",
      headline: t("Writes differently from earlier work"),
      detail: changes.length > 0 ? `${changes[0]} ${count}` : `${t("The small words the student usually uses (prepositions, conjunctions) changed.")} ${count}`,
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
  const explained = styleBaselineText(ev);
  if (explained) return { key: "style", title, status: "wait", headline: t("Nothing to compare with yet"), detail: explained };
  return {
    key: "style",
    title,
    status: "wait",
    headline: t("{have} of {need} earlier works so far", { have: baseline?.have ?? 0, need: baseline?.need ?? 3 }),
    detail: t("A student is only compared with themselves once there is enough of their work, so nobody is flagged on their first pieces."),
  };
}

interface Ref {
  kind: string;
  status: string;
  detail: string;
}

export function splitRefs(ev: Evidence): { sources: Ref[]; quotes: Ref[] } {
  const refs = (ev.references as Ref[] | undefined) ?? [];
  return { sources: refs.filter((r) => r.kind !== "quote"), quotes: refs.filter((r) => r.kind === "quote") };
}

function sourceCheck(submission: Submission, student: boolean): Check | null {
  const result = byName(submission, "text_citations");
  if (!result) return null;
  const title = t("Sources");
  if (result.verdict === "error") return broken("sources", title, student, submission);
  const ev = evidence(result);
  const { sources, quotes } = splitRefs(ev);
  const missing = sources.filter((r) => r.status === "missing").length;
  const found = sources.filter((r) => r.status === "found").length;
  const notCovered = sources.filter((r) => r.status === "unchecked" && NOT_COVERED.includes(r.detail)).length;
  const next = t("Next step: ask the student to show the books and articles from the list.");
  if (sources.length === 0) {
    if (ev.sources_expected === true) return { key: "sources", title, status: "look", headline: t("Research text with no sources") };
    if (quotes.length > 0) {
      const quotesFound = quotes.filter((r) => r.status === "found").length;
      return { key: "sources", title, status: "off", headline: t("No list of sources"), detail: t("Quotes found on the web: {found} of {total}.", { found: quotesFound, total: quotes.length }) };
    }
    return { key: "sources", title, status: "off", headline: t("No sources cited") };
  }
  if (result.verdict === "suspicious" && missing > 0) {
    return {
      key: "sources",
      title,
      status: "alert",
      headline: t("{missing} of {total} sources do not seem to exist", { missing, total: sources.length }),
      detail: t("Invented references are a common trace of chatbot writing. The list is below."),
      next,
    };
  }
  if (missing > 0) return { key: "sources", title, status: "look", headline: t("{missing} of {total} sources not found", { missing, total: sources.length }), next };
  if (found > 0 && found === sources.length) return { key: "sources", title, status: "ok", headline: tn(found, "The cited source exists", "All {n} sources exist") };
  if (found > 0 && found + notCovered === sources.length) {
    return { key: "sources", title, status: "ok", headline: t("{found} of {total} sources found, the rest are not in open catalogues", { found, total: sources.length }) };
  }
  if (found > 0) return { key: "sources", title, status: "ok", headline: t("{found} of {total} sources found, the rest could not be checked", { found, total: sources.length }) };
  if (notCovered > 0) return { key: "sources", title, status: "off", headline: t("These books are not in open catalogues"), detail: t("Open catalogues cover few Russian books. Check the list by hand.") };
  return { key: "sources", title, status: "off", headline: t("Sources could not be checked right now") };
}

export function promptText(value: unknown): string {
  if (typeof value !== "string") return "";
  const flat = value.replace(/\s+/g, " ").trim();
  return flat.length > PROMPT_CHARS ? `${flat.slice(0, PROMPT_CHARS).trimEnd()}…` : flat;
}

function shadowCheck(submission: Submission, student: boolean): Check | null {
  const result = byName(submission, "text_shadow");
  if (!result) return null;
  const title = t("AI answers to the task");
  if (result.verdict === "error") return student ? null : { key: "shadow", title, status: "off", headline: t("Comparison failed, try re-analyzing later") };
  const ev = evidence(result);
  const share = num(ev.share);
  if (share === null) {
    if (ev.reason === "not a class submission") return null;
    if (ev.reason === "text too short to compare") return { key: "shadow", title, status: "off", headline: t("Too short to compare with AI answers") };
    if (student) return null;
    if (ev.reason === "AI answers were created after this work was handed in") {
      return { key: "shadow", title, status: "off", headline: t("AI answers were made after this work was handed in"), detail: t("Only work handed in after the AI answers were made is compared with them.") };
    }
    return {
      key: "shadow",
      title,
      status: "off",
      headline: t("No AI answers generated yet"),
      detail: t("Generate AI answers to the assignment on the class page to compare student work with them."),
    };
  }
  if (result.verdict === "suspicious") {
    return {
      key: "shadow",
      title,
      status: "alert",
      headline: student ? t("Much of the text repeats an AI answer to the assignment") : t("Follows an AI answer: {n}% of sentences, same order", { n: Math.round(share * 100) }),
    };
  }
  const prompt = promptText(ev.prompt);
  const compared = num(ev.answers_for_prompt) ?? num(ev.answers_compared);
  if (prompt && compared) {
    return { key: "shadow", title, status: "ok", headline: tn(compared, "Not like the {n} AI answer to «{prompt}»", "Not like any of the {n} AI answers to «{prompt}»", { prompt }) };
  }
  return { key: "shadow", title, status: "ok", headline: t("Different from AI answers to this task") };
}

export function textChecks(submission: Submission, student = false): Check[] {
  const checks: ((submission: Submission, student: boolean) => Check | null)[] = [aiCheck, copyCheck, trickCheck, ageCheck, styleCheck, sourceCheck, shadowCheck];
  return checks.map((fn) => fn(submission, student)).filter((c): c is Check => c !== null);
}

export const PLAIN_VERDICT: Record<string, { teacher: string; student: string; status: CheckStatus }> = {
  authentic: { teacher: msg("Looks like the student's own work"), student: msg("Your work passed the checks"), status: "ok" },
  authentic_edited: { teacher: msg("Looks like the student's own work"), student: msg("Your work passed the checks"), status: "ok" },
  needs_review: { teacher: msg("Worth a closer look"), student: msg("Your teacher may ask you about this work"), status: "look" },
  suspicious: { teacher: msg("Worth a conversation with the student"), student: msg("Your teacher may ask you about this work"), status: "look" },
  likely_fake: { teacher: msg("Strong signs the student did not write this"), student: msg("Your teacher will want to talk about this work"), status: "alert" },
  fake: { teacher: msg("Strong signs the student did not write this"), student: msg("Your teacher will want to talk about this work"), status: "alert" },
  inconclusive: { teacher: msg("No clear signs of AI, but no firm answer either"), student: msg("No clear answer yet"), status: "wait" },
};

const RANK: Record<CheckStatus, number> = { off: 0, wait: 1, ok: 2, look: 3, alert: 4 };
const NEXT_ORDER = ["copy", "tricks", "sources", "shadow", "ai", "style", "age"];

export function plainOutcome(verdict: string, originality: number | null, note: string | null, student: boolean): { text: string; status: CheckStatus; showRisk: boolean } {
  const base = PLAIN_VERDICT[verdict] ?? PLAIN_VERDICT.inconclusive;
  let text = student ? base.student : base.teacher;
  let status = base.status;
  let showRisk = verdict !== "inconclusive" && verdict !== "";
  if ((verdict === "inconclusive" || verdict === "") && note === "too_short") {
    text = student ? msg("Too short to check for AI writing") : msg("Too short to check for AI writing (needs about 90 words)");
    status = "wait";
  }
  if (originality != null && originality < 60 && RANK[status] < RANK.alert) {
    text = student ? msg("Matches with other texts were found in the work") : msg("Most of the text was found in other sources");
    status = "alert";
    showRisk = false;
  } else if (originality != null && originality < 85 && RANK[status] < RANK.look) {
    text = student ? msg("Part of the text matches other sources") : msg("Part of the text matches other sources; worth a look");
    status = "look";
    showRisk = false;
  }
  return { text, status, showRisk };
}

export function summaryOutcome(submission: Submission, checks: Check[], student: boolean): { text: string; status: CheckStatus } {
  const note = evidence(byName(submission, "text_classifier")).reason === "text too short for a verdict" ? "too_short" : null;
  const report = submission.originality;
  const plain = plainOutcome(submission.final_verdict, report?.status === "done" ? report.originality ?? null : null, note, student);
  const raised = checks.filter((c) => c.status === "alert" || c.status === "look");
  if (raised.length > 0 && RANK[plain.status] < RANK.look) {
    return { text: student ? msg("Your teacher may ask you about this work") : msg("Worth a closer look"), status: "look" };
  }
  const inconclusive = submission.final_verdict === "inconclusive" || submission.final_verdict === "";
  const cleared = checks.some((c) => c.status === "ok");
  if (inconclusive && raised.length === 0 && cleared && note === null) return { text: msg("No clear warning signs found"), status: "ok" };
  return { text: plain.text, status: plain.status };
}

export function nextStep(checks: Check[]): string {
  const raised = checks.filter((c) => c.status === "alert" || c.status === "look");
  const worst = Math.max(...raised.map((c) => RANK[c.status]));
  const top = raised
    .filter((c) => RANK[c.status] === worst)
    .sort((a, b) => NEXT_ORDER.indexOf(a.key) - NEXT_ORDER.indexOf(b.key))[0];
  return top?.next ?? t(GENERIC_NEXT);
}

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

function SummaryBlock({ status, headline, children }: { status: CheckStatus; headline: string; children?: React.ReactNode }) {
  const tone = STATUS_STYLE[status];
  return (
    <div className={clsx("border-l-4 pl-4 py-1", tone.bar)}>
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("In short")}</div>
      <h3 className={clsx("font-display text-2xl sm:text-3xl leading-tight mt-1", tone.text)}>{headline}</h3>
      {children}
    </div>
  );
}

type MediaKind = "image" | "audio" | "video";

function mediaKind(submission: Submission): MediaKind | null {
  if (submission.mime_type?.startsWith("image/")) return "image";
  if (submission.mime_type?.startsWith("audio/")) return "audio";
  if (submission.mime_type?.startsWith("video/")) return "video";
  return null;
}

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

function generatorName(meta: Evidence): string | null {
  const mark = meta.watermark as Evidence | null | undefined;
  if (mark && typeof mark.name === "string") return mark.name;
  const trace = (meta.ai_trace as Evidence[] | undefined) ?? [];
  const named = trace.find((x) => typeof x.generator === "string" && x.generator);
  return named ? String(named.generator) : null;
}

export function mediaOutcome(submission: Submission, student: boolean): { text: string; status: CheckStatus; detail?: string } | null {
  const kind = mediaKind(submission);
  if (!kind || !submission.analysis_results?.length) return null;
  const meta = evidence(byName(submission, "metadata"));
  const verdict = submission.final_verdict;
  const votes = MEDIA_DETECTORS.map((name) => byName(submission, name)).filter((r): r is AnalysisResult => !!r && VOTED.has(r.verdict));
  const flagged = votes.filter((r) => FLAGGED.has(r.verdict)).length;
  const tally = flagged > 0 ? t("Checks that think so: {n} of {m}.", { n: flagged, m: votes.length }) : undefined;
  if (meta.provenance_proof === true) {
    const generator = generatorName(meta);
    return {
      text: student ? t(PLAIN_VERDICT.fake.student) : t(MEDIA_MADE[kind]),
      status: "alert",
      detail: generator
        ? t("The file carries an invisible mark from {generator}. Phones and cameras do not add such a mark.", { generator })
        : t("The file carries an invisible mark of an AI generator. Phones and cameras do not add such a mark."),
    };
  }
  if (student) {
    const base = PLAIN_VERDICT[verdict] ?? PLAIN_VERDICT.inconclusive;
    return { text: t(base.student), status: base.status };
  }
  if (verdict === "fake" || verdict === "likely_fake") return { text: t(MEDIA_LIKELY[kind]), status: "alert", detail: tally };
  if (verdict === "suspicious" || verdict === "needs_review") return { text: t("Worth a closer look"), status: "look", detail: tally };
  if (verdict === "authentic" || verdict === "authentic_edited") return { text: t("No signs of an AI generator found"), status: "ok" };
  return { text: t("No clear answer"), status: "wait", detail: flagged > 0 && flagged < votes.length ? t("The checks disagree: {n} of {m} see signs of an AI generator.", { n: flagged, m: votes.length }) : undefined };
}

function MediaSummary({ submission, student }: { submission: Submission; student: boolean }) {
  const kind = mediaKind(submission);
  const outcome = mediaOutcome(submission, student);
  if (!kind || !outcome) return null;
  const raised = outcome.status === "alert" || outcome.status === "look";
  return (
    <section className="px-4 sm:px-6 py-5 border-b border-ink-700">
      <SummaryBlock status={outcome.status} headline={outcome.text}>
        {outcome.detail && <p className="text-sm text-ink-300 mt-2 leading-relaxed">{outcome.detail}</p>}
        {!student && raised && <p className="text-sm text-ink-100 mt-2 leading-relaxed">{t(MEDIA_NEXT[kind])}</p>}
      </SummaryBlock>
    </section>
  );
}

export default function TeacherSummary({ submission, student }: { submission: Submission; student: boolean }) {
  if (submission.status !== "completed") return null;
  if (!isTextSubmission(submission)) return <MediaSummary submission={submission} student={student} />;
  const checks = textChecks(submission, student);
  const outcome = summaryOutcome(submission, checks, student);
  const raised = checks.filter((c) => c.status === "alert" || c.status === "look");
  const waiting = checks.filter((c) => c.status === "wait" && c.key !== "copy");
  const copyRunning = checks.some((c) => c.key === "copy" && c.status === "wait");
  const waitingNote = student
    ? tn(waiting.length, "{n} check will say more once there is more of your work.", "{n} checks will say more once there is more of your work.")
    : tn(waiting.length, "{n} check will say more once there is more of this student's work.", "{n} checks will say more once there is more of this student's work.");

  return (
    <section className="px-4 sm:px-6 py-5 border-b border-ink-700">
      <SummaryBlock status={outcome.status} headline={t(outcome.text)}>
        <p className="text-sm text-ink-300 mt-2 leading-relaxed">
          {raised.length > 0
            ? t("Raised by: {reasons}.", { reasons: raised.map((c) => lowerFirst(c.headline)).join("; ") })
            : RANK[outcome.status] < RANK.look && t("No check raised a concern.")}
          {waiting.length > 0 && ` ${waitingNote}`}
          {copyRunning && ` ${t("Comparison with other work is still running.")}`}
        </p>
        {!student && raised.length > 0 && <p className="text-sm text-ink-100 mt-2 leading-relaxed">{nextStep(checks)}</p>}
      </SummaryBlock>
      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3 mt-5">
        {checks.map((c) => <Tile key={c.key} check={c} />)}
      </div>
    </section>
  );
}
