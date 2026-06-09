import { useState } from "react";
import clsx from "clsx";
import { useFactCheck } from "../hooks/useFactCheck";
import type { FactCheckResult } from "../types";

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

const SAMPLE_PROMPTS = [
  "The Eiffel Tower was completed in 1889 and is located in Berlin.",
  "Scientists discovered water on Mars in 2008. The planet has two moons named Phobos and Deimos.",
  "ChatGPT was released by OpenAI in November 2022 and reached 100 million users in two months.",
];

export default function FactCheckPage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<FactCheckResult | null>(null);
  const { mutate: check, isPending, isError } = useFactCheck();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setResult(null);
    check(text, { onSuccess: setResult });
  };

  const verdict = result ? (VERDICT_TONE[result.overall_verdict] ?? VERDICT_TONE.no_claims) : null;

  return (
    <div className="max-w-3xl animate-rise">
      <div className="mb-8">
        <span className="label-mono">Service / 03</span>
        <h1 className="font-display text-5xl lg:text-6xl text-ink-50 leading-none mt-3">
          Fact <span className="italic text-signal-amber">Check</span>
        </h1>
        <p className="text-ink-400 mt-3 leading-relaxed max-w-xl">
          Paste text. NER + LLM extract claims, cross-referenced against Google Fact Check.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="case-card crop-marks">
        <div className="flex items-center justify-between px-6 py-3 border-b border-ink-700">
          <div className="flex items-center gap-3">
            <span className={clsx("w-1.5 h-1.5 rounded-full", isPending ? "bg-signal-amber pulse-dot" : "bg-signal-cyan")} />
            <span className="label-mono">Claim Extractor</span>
          </div>
          <span className="font-mono text-[10px] text-ink-500 ticker">
            {text.length} / 10000 CHARS
          </span>
        </div>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste article text, news excerpt, or any text with factual claims…"
          rows={8}
          maxLength={10000}
          className="w-full px-5 py-4 font-mono text-sm text-ink-100 resize-y focus:outline-none border-0 placeholder:text-ink-500 appearance-none"
          style={{ background: "transparent", colorScheme: "dark" }}
        />

        <div className="flex items-center justify-between px-6 py-3 border-t border-ink-700 gap-3 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
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
          </div>
          <button
            type="submit"
            disabled={isPending || !text.trim()}
            className="btn-forensic"
          >
            {isPending ? "Analyzing…" : "Run Pipeline →"}
          </button>
        </div>
      </form>

      {isPending && (
        <div className="mt-6 case-card crop-marks p-6 animate-fade-in">
          <div className="flex items-center gap-3 mb-5">
            <span className="w-1.5 h-1.5 rounded-full bg-signal-amber pulse-dot" />
            <span className="label-mono text-signal-amber">Pipeline Running</span>
          </div>
          <div className="space-y-3">
            {[
              "Extracting named entities via spaCy NER",
              "Splitting compound sentences into atomic claims",
              "Fetching web context via DuckDuckGo",
              "Assessing claims with qwen2.5:3b",
              "Cross-referencing Google Fact Check API",
            ].map((step, i) => (
              <div key={i} className="flex items-center gap-3" style={{ animationDelay: `${i * 0.18}s` }}>
                <span className="font-mono text-[10px] text-ink-600 w-5 shrink-0">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div className="flex-1 h-px bg-ink-800 relative overflow-hidden">
                  <div
                    className="absolute inset-y-0 left-0 bg-signal-amber/40"
                    style={{
                      width: "40%",
                      animation: `scan 1.8s ease-in-out ${i * 0.18}s infinite`,
                    }}
                  />
                </div>
                <span className="font-mono text-[10px] text-ink-500 text-right">{step}</span>
              </div>
            ))}
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
        <div className="mt-6 space-y-4 animate-fade-in-up">
          <div className="case-card crop-marks p-6 flex items-center justify-between">
            <div>
              <span className="label-mono">Overall Verdict</span>
              <div className={clsx("font-display text-4xl mt-2", verdict.color)}>{verdict.label}</div>
              <div className="font-mono text-[11px] text-ink-400 mt-1 ticker">
                {result.claims_count} claim{result.claims_count !== 1 ? "s" : ""} extracted · {result.claims.filter(c => c.assessment === "likely_true").length} verified · {result.claims.filter(c => c.assessment === "likely_false").length} disputed
              </div>
            </div>
            <span className={clsx("badge border-current", verdict.color)}>
              {verdict.label}
            </span>
          </div>

          {result.claims.map((claim, i) => (
            <div key={i} className="case-card crop-marks p-5 lift">
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <span className="font-mono text-xs text-ink-500 ticker shrink-0 mt-0.5">
                    #{String(i + 1).padStart(2, "0")}
                  </span>
                  <p className="text-ink-100 leading-relaxed flex-1">{claim.claim}</p>
                </div>
                <span className={clsx("badge border-current shrink-0", ASSESSMENT_TONE[claim.assessment])}>
                  {ASSESSMENT_LABELS[claim.assessment]}
                </span>
              </div>
              {claim.explanation && (
                <p className="text-sm text-ink-400 leading-relaxed pl-9">{claim.explanation}</p>
              )}
              {claim.fact_checks.length > 0 && (
                <div className="mt-3 pl-9 pt-3 border-t border-dashed border-ink-700 space-y-1.5">
                  <div className="label-mono mb-2">External Sources</div>
                  {claim.fact_checks.map((fc, j) => (
                    <a
                      key={j}
                      href={fc.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-3 font-mono text-xs text-signal-cyan hover:underline"
                    >
                      <span className="text-ink-500 uppercase tracking-[0.12em] text-[10px] min-w-[80px]">{fc.publisher}</span>
                      <span>→</span>
                      <span>{fc.rating}</span>
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
