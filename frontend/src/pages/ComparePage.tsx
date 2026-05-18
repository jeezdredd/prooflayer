import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { content } from "../api/endpoints";
import { useDashboard } from "../hooks/useDashboard";
import type { Submission } from "../types";

const VERDICT_COLOR: Record<string, string> = {
  authentic: "text-sage-300 border-sage-500/40 bg-sage-500/10",
  suspicious: "text-signal-amber border-signal-amber/40 bg-signal-amber/10",
  fake: "text-signal-blood border-signal-blood/40 bg-signal-blood/10",
  likely_fake: "text-signal-blood border-signal-blood/40 bg-signal-blood/10",
  inconclusive: "text-ink-400 border-ink-700 bg-ink-800/40",
};

function SubmissionPicker({
  label,
  value,
  onChange,
  options,
  excludeId,
}: {
  label: string;
  value: string;
  onChange: (id: string) => void;
  options: Array<{ id: string; original_filename: string; created_at: string; final_verdict: string }>;
  excludeId?: string;
}) {
  return (
    <label className="block">
      <span className="label-mono">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full bg-ink-950/70 border border-ink-700 px-3 py-2 text-sm font-mono text-ink-100 focus:outline-none focus:border-iris transition"
      >
        <option value="">Select submission...</option>
        {options
          .filter((o) => o.id !== excludeId)
          .map((o) => (
            <option key={o.id} value={o.id}>
              {o.original_filename} ({o.final_verdict || "pending"})
            </option>
          ))}
      </select>
    </label>
  );
}

function SideCard({ submission }: { submission: Submission }) {
  const verdictCls = VERDICT_COLOR[submission.final_verdict] || VERDICT_COLOR.inconclusive;
  return (
    <div className="case-card crop-marks p-5 animate-fade-in-up">
      <div className="flex items-start justify-between mb-3">
        <div className="min-w-0">
          <div className="font-mono text-sm text-ink-100 truncate">{submission.original_filename}</div>
          <div className="font-mono text-[10px] text-ink-500 mt-0.5 ticker">
            {submission.mime_type} &middot; {(submission.file_size / 1024).toFixed(0)} KB
          </div>
        </div>
        <span className={clsx("badge border", verdictCls)}>
          {submission.final_verdict || "-"}
        </span>
      </div>

      {submission.final_score != null && (
        <div className="mb-4">
          <div className="font-display text-3xl text-white tabular-nums">
            {(submission.final_score * 100).toFixed(0)}%
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">fake probability</div>
          <div className="mt-2 h-1 bg-ink-800 overflow-hidden">
            <div
              className={clsx("h-full transition-all", {
                "bg-sage-400": submission.final_score < 0.3,
                "bg-signal-amber": submission.final_score >= 0.3 && submission.final_score < 0.5,
                "bg-orange-500": submission.final_score >= 0.5 && submission.final_score < 0.7,
                "bg-signal-blood": submission.final_score >= 0.7,
              })}
              style={{ width: `${submission.final_score * 100}%` }}
            />
          </div>
        </div>
      )}

      <div className="space-y-2">
        {submission.analysis_results.map((r) => {
          const cls = VERDICT_COLOR[r.verdict] || VERDICT_COLOR.inconclusive;
          return (
            <div key={r.id} className="flex items-center justify-between text-xs border-b border-ink-800 pb-1.5">
              <span className="text-ink-200 font-mono">{r.analyzer_name}</span>
              <div className="flex items-center gap-2">
                <span className="text-ink-400 font-mono tabular-nums">{(r.confidence * 100).toFixed(0)}%</span>
                <span className={clsx("px-1.5 py-0.5 font-mono uppercase text-[10px] border", cls)}>
                  {r.verdict || "-"}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialA = searchParams.get("a") || "";
  const initialB = searchParams.get("b") || "";
  const [idA, setIdA] = useState(initialA);
  const [idB, setIdB] = useState(initialB);

  const { data: list } = useDashboard({ page: "1", page_size: "100" });

  useEffect(() => {
    const params: Record<string, string> = {};
    if (idA) params.a = idA;
    if (idB) params.b = idB;
    setSearchParams(params, { replace: true });
  }, [idA, idB, setSearchParams]);

  const ready = !!idA && !!idB;
  const compareQuery = useQuery({
    queryKey: ["compare", idA, idB],
    queryFn: () => content.compare([idA, idB]).then((r) => r.data),
    enabled: ready,
  });

  const options = useMemo(() => list?.results || [], [list]);
  const pair = compareQuery.data;
  const diffScore =
    pair && pair[0].final_score != null && pair[1].final_score != null
      ? Math.abs(pair[0].final_score - pair[1].final_score) * 100
      : null;

  return (
    <div>
      <div className="mb-6">
        <span className="label-mono">Service / 05</span>
        <h1 className="font-display text-4xl text-white mt-2">Compare</h1>
        <p className="text-sm text-ink-400 mt-2">
          Pick two submissions to view scores and analyzer breakdowns side by side.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <SubmissionPicker label="Left" value={idA} onChange={setIdA} options={options} excludeId={idB} />
        <SubmissionPicker label="Right" value={idB} onChange={setIdB} options={options} excludeId={idA} />
      </div>

      {!ready && (
        <div className="text-center py-16 font-mono text-xs uppercase tracking-[0.14em] text-ink-500 border border-dashed border-ink-700">
          Select two submissions above to compare.
        </div>
      )}

      {ready && compareQuery.isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin w-6 h-6 border-2 border-iris border-t-transparent rounded-full" />
        </div>
      )}

      {ready && compareQuery.isError && (
        <div className="text-center py-10 font-mono text-sm text-signal-blood">
          Failed to load comparison.
        </div>
      )}

      {pair && pair.length === 2 && (
        <>
          {diffScore != null && (
            <div className="mb-4 px-4 py-3 bg-iris/10 border border-iris/40 font-mono text-sm text-iris-light">
              Score difference: <span className="font-bold">{diffScore.toFixed(0)} pts</span>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SideCard submission={pair[0]} />
            <SideCard submission={pair[1]} />
          </div>
        </>
      )}
    </div>
  );
}
