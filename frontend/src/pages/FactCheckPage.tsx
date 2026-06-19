import clsx from "clsx";
import { useFactCheck } from "../hooks/useFactCheck";
import { useEffect, useRef, useState } from "react";
import type { FactCheckMode, FactCheckStage } from "../types";
import SubscriptionGate from "../components/SubscriptionGate";
import { factcheck } from "../api/endpoints";

const VERDICT_TONE: Record<string, { color: string; label: string }> = {
  mostly_accurate: { color: "text-signal-sage", label: "Mostly Accurate" },
  mixed: { color: "text-signal-amber", label: "Mixed Findings" },
  misleading: { color: "text-signal-blood", label: "Misleading" },
  no_claims: { color: "text-ink-300", label: "No Claims Found" },
};

const ASSESSMENT_TONE: Record<string, string> = {
  likely_true: "text-signal-sage",
  likely_false: "text-signal-blood",
  uncertain: "text-signal-amber",
};

const ASSESSMENT_LABELS: Record<string, string> = {
  likely_true: "Likely True",
  likely_false: "Likely False",
  uncertain: "Uncertain",
};

const ASSESSMENT_BG: Record<string, string> = {
  likely_true: "bg-signal-sage/25 text-signal-sage",
  likely_false: "bg-signal-blood/25 text-signal-blood",
  uncertain: "bg-signal-amber/25 text-signal-amber",
};

const SAMPLE_PROMPTS = [
  "The Eiffel Tower was completed in 1889 and is located in Berlin.",
  "Scientists discovered water on Mars in 2008. The planet has two moons named Phobos and Deimos.",
  "ChatGPT was released by OpenAI in November 2022 and reached 100 million users in two months.",
];

const STAGES: Array<{ key: FactCheckStage; label: string }> = [
  { key: "extracting", label: "Extracting named entities via spaCy NER" },
  { key: "searching", label: "Fetching DuckDuckGo + Wikipedia context" },
  { key: "assessing", label: "Assessing claims with qwen2.5" },
  { key: "cross_referencing", label: "Cross-referencing Google Fact Check" },
  { key: "done", label: "Complete" },
];

const STAGE_ORDER: FactCheckStage[] = ["pending", "extracting", "searching", "assessing", "cross_referencing", "done"];

function stageIndex(stage: FactCheckStage | null): number {
  if (!stage) return 0;
  return STAGE_ORDER.indexOf(stage);
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function HighlightedText({
  text,
  claims,
  activeIdx,
  onClick,
}: {
  text: string;
  claims: Array<{ claim: string; assessment: string }>;
  activeIdx: number | null;
  onClick: (i: number) => void;
}) {
  if (!text || claims.length === 0) {
    return <pre className="whitespace-pre-wrap font-mono text-xs text-ink-300 leading-relaxed">{text}</pre>;
  }

  const matches: Array<{ start: number; end: number; idx: number }> = [];
  claims.forEach((c, i) => {
    if (!c.claim) return;
    const re = new RegExp(escapeRegex(c.claim.trim()), "i");
    const m = text.match(re);
    if (m && m.index !== undefined) {
      matches.push({ start: m.index, end: m.index + m[0].length, idx: i });
    }
  });
  matches.sort((a, b) => a.start - b.start);

  const parts: React.ReactNode[] = [];
  let cursor = 0;
  matches.forEach((m, k) => {
    if (cursor < m.start) parts.push(<span key={`t-${k}`}>{text.slice(cursor, m.start)}</span>);
    const claim = claims[m.idx];
    const bg = ASSESSMENT_BG[claim.assessment] ?? "bg-signal-amber/20";
    const active = activeIdx === m.idx;
    parts.push(
      <span
        key={`m-${m.idx}`}
        id={`mark-${m.idx}`}
        onClick={() => onClick(m.idx)}
        className={clsx(
          "cursor-pointer rounded-sm px-0.5 transition-all",
          bg,
          active && "ring-1 ring-signal-amber ring-offset-1 ring-offset-ink-900",
        )}
      >
        {text.slice(m.start, m.end)}
      </span>,
    );
    cursor = m.end;
  });
  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);

  return <pre className="whitespace-pre-wrap font-mono text-xs text-ink-300 leading-relaxed">{parts}</pre>;
}

function FactCheckPageInner() {
  const [mode, setMode] = useState<FactCheckMode>("text");
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [submittedText, setSubmittedText] = useState("");
  const [activeClaim, setActiveClaim] = useState<number | null>(null);
  const [fetching, setFetching] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [ioError, setIoError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const { submit, isPending, isError, stage, progress, result } = useFactCheck();

  useEffect(() => {
    if (activeClaim === null) return;
    const el = document.getElementById(`mark-${activeClaim}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [activeClaim]);

  const runSubmit = (body: string) => {
    if (!body.trim()) return;
    setSubmittedText(body);
    setActiveClaim(null);
    setIoError(null);
    submit(body);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runSubmit(text);
  };

  const handleFetchUrl = async () => {
    if (!url.trim()) return;
    setFetching(true);
    setIoError(null);
    try {
      const res = await factcheck.fetchUrl(url.trim());
      const t = res.data.text;
      setText(t);
      runSubmit(t);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } } };
      setIoError(e?.response?.data?.error || "URL fetch failed");
    } finally {
      setFetching(false);
    }
  };

  const handleDoc = async (file: File) => {
    setFetching(true);
    setIoError(null);
    try {
      const res = await factcheck.extractDoc(file);
      const t = res.data.text;
      setText(t);
      runSubmit(t);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } } };
      setIoError(e?.response?.data?.error || "Document extract failed");
    } finally {
      setFetching(false);
    }
  };

  const handleExport = async () => {
    if (!result) return;
    setExporting(true);
    try {
      const res = await factcheck.exportPdf(result, submittedText);
      const blob = new Blob([res.data as unknown as BlobPart], { type: "application/pdf" });
      const u = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = u;
      a.download = `factcheck-${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(u);
    } finally {
      setExporting(false);
    }
  };

  const verdict = result ? (VERDICT_TONE[result.overall_verdict] ?? VERDICT_TONE.no_claims) : null;
  const currentStageIndex = stageIndex(stage);

  return (
    <div className="max-w-5xl animate-rise">
      <div className="mb-8">
        <span className="label-mono">Service / 03</span>
        <h1 className="font-display text-5xl lg:text-6xl text-ink-50 leading-none mt-3">
          Fact <span className="italic text-signal-amber">Check</span>
        </h1>
        <p className="text-ink-400 mt-3 leading-relaxed max-w-xl">
          Paste text, URL, or upload PDF/DOCX. NER + LLM extract claims, cross-referenced against Wikipedia + Google Fact Check.
        </p>
      </div>

      <div className="flex items-center gap-2 mb-4">
        {(["text", "url", "document"] as FactCheckMode[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={clsx(
              "font-mono text-[10px] uppercase tracking-[0.14em] px-3 py-1.5 rounded-sm border transition-colors",
              mode === m
                ? "border-signal-amber text-signal-amber bg-signal-amber/5"
                : "border-white/10 text-ink-400 hover:border-signal-amber/60 hover:text-signal-amber",
            )}
          >
            {m}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="case-card crop-marks">
        <div className="flex items-center justify-between px-6 py-3 border-b border-ink-700">
          <div className="flex items-center gap-3">
            <span className={clsx("w-1.5 h-1.5 rounded-full", isPending ? "bg-signal-amber pulse-dot" : "bg-signal-cyan")} />
            <span className="label-mono">Claim Extractor / {mode}</span>
          </div>
          {mode === "text" && (
            <span className="font-mono text-[10px] text-ink-500 ticker">
              {text.length} / 10000 CHARS
            </span>
          )}
        </div>

        {mode === "text" && (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste article text, news excerpt, or any text with factual claims..."
            rows={8}
            maxLength={10000}
            className="w-full px-5 py-4 font-mono text-sm text-ink-100 resize-y focus:outline-none border-0 placeholder:text-ink-500 appearance-none"
            style={{ background: "transparent", colorScheme: "dark" }}
          />
        )}

        {mode === "url" && (
          <div className="px-5 py-4">
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/article"
              className="w-full px-3 py-2 font-mono text-sm text-ink-100 bg-white/[0.02] border border-white/10 rounded-sm focus:outline-none focus:border-signal-amber"
            />
            <p className="font-mono text-[10px] text-ink-500 mt-2">
              Fetches article text via Trafilatura. SSRF-guarded (no private IPs).
            </p>
          </div>
        )}

        {mode === "document" && (
          <div className="px-5 py-4">
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleDoc(f);
              }}
              className="w-full font-mono text-xs text-ink-300 file:mr-3 file:px-3 file:py-1.5 file:bg-white/[0.04] file:border file:border-white/10 file:rounded-sm file:font-mono file:text-[10px] file:uppercase file:tracking-[0.14em] file:text-signal-amber hover:file:border-signal-amber/60"
            />
            <p className="font-mono text-[10px] text-ink-500 mt-2">
              PDF or DOCX, max 10 MB. Extracted text is sent to the pipeline.
            </p>
          </div>
        )}

        <div className="flex items-center justify-between px-6 py-3 border-t border-ink-700 gap-3 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            {mode === "text" && (
              <>
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">Try:</span>
                {SAMPLE_PROMPTS.map((s, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setText(s)}
                    className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-300 hover:text-signal-amber border border-white/10 hover:border-signal-amber/60 px-2.5 py-1 rounded-sm transition-colors bg-white/[0.02]"
                  >
                    Sample {String(i + 1).padStart(2, "0")}
                  </button>
                ))}
              </>
            )}
          </div>
          {mode === "text" && (
            <button type="submit" disabled={isPending || !text.trim()} className="btn-forensic">
              {isPending ? "Analyzing..." : "Run Pipeline ->"}
            </button>
          )}
          {mode === "url" && (
            <button
              type="button"
              onClick={handleFetchUrl}
              disabled={fetching || isPending || !url.trim()}
              className="btn-forensic"
            >
              {fetching ? "Fetching..." : "Fetch + Analyze ->"}
            </button>
          )}
        </div>
      </form>

      {ioError && (
        <div className="mt-4 p-4 border border-signal-blood bg-signal-blood/5 flex items-center gap-3 animate-fade-in">
          <span className="w-5 h-5 border border-signal-blood text-signal-blood text-[10px] font-bold flex items-center justify-center">!</span>
          <span className="font-mono text-xs text-signal-blood">{ioError}</span>
        </div>
      )}

      {isPending && (
        <div className="mt-6 case-card crop-marks p-6 animate-fade-in">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <span className="w-1.5 h-1.5 rounded-full bg-signal-amber pulse-dot" />
              <span className="label-mono text-signal-amber">Pipeline Running</span>
            </div>
            <span className="font-mono text-[11px] text-ink-500">{progress}%</span>
          </div>
          <div className="h-px bg-ink-800 mb-5 relative overflow-hidden">
            <div className="absolute inset-y-0 left-0 bg-signal-amber/60 transition-all duration-700" style={{ width: `${progress}%` }} />
          </div>
          <div className="space-y-3">
            {STAGES.filter((s) => s.key !== "done").map((s, i) => {
              const sIdx = STAGE_ORDER.indexOf(s.key);
              const done = sIdx < currentStageIndex;
              const active = sIdx === currentStageIndex;
              return (
                <div key={s.key} className="flex items-center gap-3">
                  <span className="font-mono text-[10px] text-ink-600 w-5 shrink-0">{String(i + 1).padStart(2, "0")}</span>
                  <div className="flex-1 h-px bg-ink-800 relative overflow-hidden">
                    {active && (
                      <div className="absolute inset-y-0 left-0 bg-signal-amber/40" style={{ width: "40%", animation: "scan 1.8s ease-in-out infinite" }} />
                    )}
                    {done && <div className="absolute inset-y-0 left-0 right-0 bg-signal-sage/40" />}
                  </div>
                  <span className={clsx("font-mono text-[10px] text-right", active ? "text-signal-amber" : done ? "text-signal-sage" : "text-ink-600")}>
                    {s.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {isError && (
        <div className="mt-4 p-4 border border-signal-blood bg-signal-blood/5 flex items-center gap-3 animate-fade-in">
          <span className="w-5 h-5 border border-signal-blood text-signal-blood text-[10px] font-bold flex items-center justify-center">!</span>
          <span className="font-mono text-xs text-signal-blood">Analysis failed. Check that Ollama is running.</span>
        </div>
      )}

      {result && verdict && (
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-5 gap-4 animate-fade-in-up">
          <div className="lg:col-span-3 space-y-4">
            <div className="case-card crop-marks p-6 flex items-center justify-between gap-4">
              <div>
                <span className="label-mono">Overall Verdict</span>
                <div className={clsx("font-display text-4xl mt-2", verdict.color)}>{verdict.label}</div>
                <div className="font-mono text-[11px] text-ink-400 mt-1 ticker">
                  {result.claims_count} claim{result.claims_count !== 1 ? "s" : ""} extracted · {result.claims.filter(c => c.assessment === "likely_true").length} verified · {result.claims.filter(c => c.assessment === "likely_false").length} disputed
                </div>
              </div>
              <div className="flex flex-col items-end gap-2">
                <span className={clsx("badge border-current", verdict.color)}>{verdict.label}</span>
                <button
                  onClick={handleExport}
                  disabled={exporting}
                  className="font-mono text-[10px] uppercase tracking-[0.14em] text-signal-amber hover:bg-signal-amber/10 border border-signal-amber/60 px-3 py-1.5 rounded-sm transition-colors"
                >
                  {exporting ? "..." : "Export PDF"}
                </button>
              </div>
            </div>

            {result.claims.map((claim, i) => (
              <div
                key={i}
                onClick={() => setActiveClaim(i)}
                className={clsx(
                  "case-card crop-marks p-5 lift cursor-pointer transition-all",
                  activeClaim === i && "ring-1 ring-signal-amber",
                )}
              >
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <span className="font-mono text-xs text-ink-500 ticker shrink-0 mt-0.5">
                      #{String(i + 1).padStart(2, "0")}
                    </span>
                    <p className="text-ink-100 leading-relaxed flex-1">{claim.claim}</p>
                  </div>
                  <span className={clsx("badge border-current shrink-0", ASSESSMENT_TONE[claim.assessment] ?? "text-signal-amber")}>
                    {ASSESSMENT_LABELS[claim.assessment] ?? "Uncertain"}
                  </span>
                </div>

                {typeof claim.confidence === "number" && (
                  <div className="pl-9 mb-3">
                    <div className="flex items-center justify-between font-mono text-[10px] text-ink-500 mb-1">
                      <span>CONFIDENCE</span>
                      <span>{claim.confidence}%</span>
                    </div>
                    <div className="h-1 bg-ink-800 relative overflow-hidden">
                      <div
                        className={clsx(
                          "absolute inset-y-0 left-0 transition-all duration-700",
                          claim.assessment === "likely_true" ? "bg-signal-sage" : claim.assessment === "likely_false" ? "bg-signal-blood" : "bg-signal-amber",
                        )}
                        style={{ width: `${claim.confidence}%` }}
                      />
                    </div>
                  </div>
                )}

                {claim.explanation && (
                  <p className="text-sm text-ink-400 leading-relaxed pl-9">{claim.explanation}</p>
                )}

                {claim.wikipedia && (
                  <div className="mt-3 pl-9 pt-3 border-t border-dashed border-ink-700">
                    <div className="label-mono mb-2">Wikipedia</div>
                    <a
                      href={claim.wikipedia.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block font-mono text-xs text-signal-cyan hover:underline mb-1"
                    >
                      {claim.wikipedia.title}
                    </a>
                    <p className="text-xs text-ink-400 leading-relaxed">{claim.wikipedia.extract.slice(0, 280)}{claim.wikipedia.extract.length > 280 ? "..." : ""}</p>
                  </div>
                )}

                {claim.sources && claim.sources.length > 0 && (
                  <div className="mt-3 pl-9 pt-3 border-t border-dashed border-ink-700 space-y-1.5">
                    <div className="label-mono mb-2">Web Sources</div>
                    {claim.sources.map((s, j) => (
                      <a
                        key={j}
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-3 font-mono text-xs text-signal-cyan hover:underline"
                      >
                        <span className="text-ink-500 shrink-0">-&gt;</span>
                        <span className="truncate">{s.title || s.url}</span>
                      </a>
                    ))}
                  </div>
                )}

                {claim.fact_checks.length > 0 && (
                  <div className="mt-3 pl-9 pt-3 border-t border-dashed border-ink-700 space-y-1.5">
                    <div className="label-mono mb-2">Fact Check Cross-Refs</div>
                    {claim.fact_checks.map((fc, j) => (
                      <a
                        key={j}
                        href={fc.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-3 font-mono text-xs text-signal-cyan hover:underline"
                      >
                        <span className="text-ink-500 uppercase tracking-[0.12em] text-[10px] min-w-[80px]">{fc.publisher}</span>
                        <span>-&gt;</span>
                        <span>{fc.rating}</span>
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="lg:col-span-2">
            <div className="case-card crop-marks p-5 sticky top-4">
              <div className="flex items-center justify-between mb-3">
                <span className="label-mono">Source Text</span>
                <span className="font-mono text-[10px] text-ink-500">{submittedText.length} chars</span>
              </div>
              <div className="max-h-[600px] overflow-y-auto">
                <HighlightedText
                  text={submittedText}
                  claims={result.claims}
                  activeIdx={activeClaim}
                  onClick={setActiveClaim}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function FactCheckPage() {
  return <SubscriptionGate feature="Fact Check"><FactCheckPageInner /></SubscriptionGate>;
}
