import { useState } from "react";
import clsx from "clsx";
import { useFactCheck } from "../hooks/useFactCheck";
import type { FactCheckResult } from "../types";

const VERDICT_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  mostly_accurate: { bg: "bg-green-100", text: "text-green-800", label: "Mostly Accurate" },
  mixed: { bg: "bg-yellow-100", text: "text-yellow-800", label: "Mixed" },
  misleading: { bg: "bg-red-100", text: "text-red-800", label: "Misleading" },
  no_claims: { bg: "bg-gray-100", text: "text-gray-700", label: "No Claims Found" },
};

const ASSESSMENT_STYLES: Record<string, string> = {
  likely_true: "text-green-700",
  likely_false: "text-red-700",
  uncertain: "text-yellow-700",
};

const ASSESSMENT_LABELS: Record<string, string> = {
  likely_true: "Likely True",
  likely_false: "Likely False",
  uncertain: "Uncertain",
};

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

  const verdict = result ? (VERDICT_STYLES[result.overall_verdict] ?? VERDICT_STYLES.no_claims) : null;

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Fact Check</h2>
      <p className="text-sm text-gray-500 mb-6">
        Paste text to extract and verify factual claims using AI analysis.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste article text, news excerpt, or any text with factual claims..."
          rows={8}
          maxLength={10000}
          className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">{text.length} / 10000</span>
          <button
            type="submit"
            disabled={isPending || !text.trim()}
            className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isPending ? "Analyzing..." : "Analyze"}
          </button>
        </div>
      </form>

      {isError && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700">Analysis failed. Check that the Ollama service is running.</p>
        </div>
      )}

      {result && verdict && (
        <div className="mt-6 space-y-4">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-gray-900">Result</h3>
              <span className={clsx("px-3 py-1 rounded-full text-sm font-medium", verdict.bg, verdict.text)}>
                {verdict.label}
              </span>
            </div>
            <p className="text-sm text-gray-500">{result.claims_count} claim{result.claims_count !== 1 ? "s" : ""} analyzed</p>
          </div>

          {result.claims.map((claim, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-start justify-between gap-3 mb-2">
                <p className="text-sm text-gray-900 flex-1">{claim.claim}</p>
                <span className={clsx("text-xs font-semibold whitespace-nowrap", ASSESSMENT_STYLES[claim.assessment])}>
                  {ASSESSMENT_LABELS[claim.assessment]}
                </span>
              </div>
              {claim.explanation && (
                <p className="text-xs text-gray-500 mb-2">{claim.explanation}</p>
              )}
              {claim.fact_checks.length > 0 && (
                <div className="mt-2 space-y-1">
                  {claim.fact_checks.map((fc, j) => (
                    <a
                      key={j}
                      href={fc.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-xs text-blue-600 hover:underline"
                    >
                      <span className="text-gray-400">{fc.publisher}:</span>
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
