import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeftRight } from "lucide-react";
import { content } from "../api/endpoints";
import { useDashboard } from "../hooks/useDashboard";
import type { AnalysisResult, Submission, SubmissionListItem } from "../types/index";
import SubscriptionGate from "../components/SubscriptionGate";

const VERDICT_COLOR: Record<string, string> = {
  authentic: "text-sage-300 border-sage-500/40 bg-sage-500/10",
  suspicious: "text-signal-amber border-signal-amber/40 bg-signal-amber/10",
  fake: "text-signal-blood border-signal-blood/40 bg-signal-blood/10",
  likely_fake: "text-signal-blood border-signal-blood/40 bg-signal-blood/10",
  inconclusive: "text-ink-400 border-ink-700 bg-ink-800/40",
  needs_review: "text-signal-violet border-signal-violet/40 bg-signal-violet/10",
};

const VERDICT_RANK: Record<string, number> = {
  authentic: 0,
  inconclusive: 1,
  needs_review: 2,
  suspicious: 3,
  likely_fake: 4,
  fake: 5,
};

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}K`;
  return `${(bytes / 1024 / 1024).toFixed(1)}M`;
}

function avgConfidence(results: AnalysisResult[]): number {
  const decisive = results.filter((r) => r.confidence > 0);
  if (!decisive.length) return 0;
  return decisive.reduce((s, r) => s + r.confidence, 0) / decisive.length;
}

function analyzersRun(sub: Submission): number {
  const total = sub.expected_analyzers.length || 1;
  const done = sub.analysis_results.length;
  return (done / total) * 100;
}

function AnimatedBar({ value, color }: { value: number; color: string }) {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setWidth(value), 80);
    return () => clearTimeout(t);
  }, [value]);
  return (
    <div className="h-1 bg-ink-800 overflow-hidden mt-1.5">
      <div
        className={clsx("h-full transition-all duration-700 ease-out", color)}
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

function MetricRow({
  label,
  display,
  barValue,
  barColor,
  highlight,
}: {
  label: string;
  display: string;
  barValue: number;
  barColor: string;
  highlight: boolean;
}) {
  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">{label}</span>
        <span className={clsx("font-display text-lg tabular-nums", highlight ? "text-sage-300" : "text-ink-100")}>
          {display}
        </span>
      </div>
      <AnimatedBar value={barValue} color={barColor} />
    </div>
  );
}

function ComparisonCard({ submission, isBetter }: { submission: Submission; isBetter: (key: string) => boolean }) {
  const verdictCls = VERDICT_COLOR[submission.final_verdict] || VERDICT_COLOR.inconclusive;
  const fakeScore = submission.final_score != null ? submission.final_score * 100 : 0;
  const confidence = avgConfidence(submission.analysis_results) * 100;
  const coverage = analyzersRun(submission);

  return (
    <div className="case-card crop-marks p-5 space-y-5 animate-fade-in-up">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-mono text-sm text-ink-100 truncate">{submission.original_filename}</div>
          <div className="font-mono text-[10px] text-ink-500 mt-0.5 ticker">
            {submission.mime_type} &middot; {formatSize(submission.file_size)}
          </div>
        </div>
        <span className={clsx("badge border shrink-0", verdictCls)}>
          {submission.final_verdict || "-"}
        </span>
      </div>

      <div className="space-y-4">
        <MetricRow
          label="Fake Probability"
          display={`${fakeScore.toFixed(0)}%`}
          barValue={fakeScore}
          barColor={isBetter("score") ? "bg-sage-400" : "bg-signal-blood"}
          highlight={isBetter("score")}
        />
        <MetricRow
          label="Avg Confidence"
          display={`${confidence.toFixed(0)}%`}
          barValue={confidence}
          barColor={isBetter("confidence") ? "bg-sage-400" : "bg-iris"}
          highlight={isBetter("confidence")}
        />
        <MetricRow
          label="Analysis Coverage"
          display={`${coverage.toFixed(0)}%`}
          barValue={coverage}
          barColor={isBetter("coverage") ? "bg-sage-400" : "bg-iris"}
          highlight={isBetter("coverage")}
        />
      </div>

      {submission.analysis_results.length > 0 && (
        <div className="space-y-1.5 pt-2 border-t border-ink-800">
          {submission.analysis_results.map((r) => {
            const cls = VERDICT_COLOR[r.verdict] || VERDICT_COLOR.inconclusive;
            return (
              <div key={r.id} className="flex items-center justify-between text-xs border-b border-ink-800 pb-1.5 last:border-0">
                <span className="text-ink-300 font-mono truncate mr-2">{r.analyzer_name}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-ink-400 font-mono tabular-nums ticker">{(r.confidence * 100).toFixed(0)}%</span>
                  <span className={clsx("px-1.5 py-0.5 font-mono uppercase text-[10px] border", cls)}>
                    {r.verdict || "-"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ComparePageInner() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("date");
  const [selected, setSelected] = useState<string[]>(() => {
    const a = searchParams.get("a");
    const b = searchParams.get("b");
    return [a, b].filter(Boolean) as string[];
  });

  const { data: list } = useDashboard({ page: "1", page_size: "100" });

  useEffect(() => {
    const params: Record<string, string> = {};
    if (selected[0]) params.a = selected[0];
    if (selected[1]) params.b = selected[1];
    setSearchParams(params, { replace: true });
  }, [selected, setSearchParams]);

  const options: SubmissionListItem[] = useMemo(() => list?.results || [], [list]);

  const filtered = useMemo(() => {
    return options.filter((s) =>
      s.original_filename.toLowerCase().includes(search.toLowerCase())
    );
  }, [options, search]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      if (sortBy === "score") {
        return (b.final_score ?? -1) - (a.final_score ?? -1);
      }
      if (sortBy === "verdict") {
        return (VERDICT_RANK[b.final_verdict] ?? 0) - (VERDICT_RANK[a.final_verdict] ?? 0);
      }
      if (sortBy === "name") return a.original_filename.localeCompare(b.original_filename);
      if (sortBy === "size") return b.file_size - a.file_size;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [filtered, sortBy]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return prev;
      return [...prev, id];
    });
  };

  const ready = selected.length === 2;

  const compareQuery = useQuery({
    queryKey: ["compare", selected[0], selected[1]],
    queryFn: () => content.compare([selected[0], selected[1]] as [string, string]).then((r) => r.data),
    enabled: ready,
  });

  const pair = compareQuery.data;

  const getBetter = (key: string) => (index: number): boolean => {
    if (!pair || pair.length !== 2) return false;
    const a = pair[0];
    const b = pair[1];
    if (key === "score") {
      const va = a.final_score ?? 1;
      const vb = b.final_score ?? 1;
      return index === 0 ? va < vb : vb < va;
    }
    if (key === "confidence") {
      const va = avgConfidence(a.analysis_results);
      const vb = avgConfidence(b.analysis_results);
      return index === 0 ? va > vb : vb > va;
    }
    if (key === "coverage") {
      const va = analyzersRun(a);
      const vb = analyzersRun(b);
      return index === 0 ? va > vb : vb > va;
    }
    return false;
  };

  const diffScore =
    pair && pair[0].final_score != null && pair[1].final_score != null
      ? Math.abs(pair[0].final_score - pair[1].final_score) * 100
      : null;

  return (
    <div className="space-y-6">
      <div>
        <span className="label-mono">Service / 05</span>
        <h1 className="font-display text-4xl text-white mt-2">Compare</h1>
        <p className="text-sm text-ink-400 mt-2">
          Select two submissions from the table to compare scores and analyzer breakdowns.
        </p>
      </div>

      {ready && compareQuery.isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin w-5 h-5 border-2 border-iris border-t-transparent rounded-full" />
        </div>
      )}

      {ready && compareQuery.isError && (
        <div className="text-center py-10 font-mono text-sm text-signal-blood">
          Failed to load comparison.
        </div>
      )}

      {pair && pair.length === 2 && (
        <div className="space-y-4">
          {diffScore != null && (
            <div className="px-4 py-3 bg-iris/10 border border-iris/40 font-mono text-sm text-iris-light flex items-center justify-between">
              <span>Score difference</span>
              <span className="font-bold tabular-nums">{diffScore.toFixed(0)} pts</span>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {pair.map((sub, idx) => (
              <ComparisonCard
                key={sub.id}
                submission={sub}
                isBetter={(key) => getBetter(key)(idx)}
              />
            ))}
          </div>

          <div className="case-card crop-marks px-5 py-4">
            <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500 mb-4">Quick Summary</div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500 mb-1">More Authentic</p>
                <p className="font-mono text-xs text-ink-100">
                  {pair[0].final_score != null && pair[1].final_score != null
                    ? pair[0].final_score < pair[1].final_score
                      ? pair[0].original_filename
                      : pair[1].original_filename
                    : "-"}
                </p>
              </div>
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500 mb-1">Higher Confidence</p>
                <p className="font-mono text-xs text-ink-100">
                  {avgConfidence(pair[0].analysis_results) >= avgConfidence(pair[1].analysis_results)
                    ? pair[0].original_filename
                    : pair[1].original_filename}
                </p>
              </div>
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500 mb-1">More Complete</p>
                <p className="font-mono text-xs text-ink-100">
                  {analyzersRun(pair[0]) >= analyzersRun(pair[1])
                    ? pair[0].original_filename
                    : pair[1].original_filename}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {!ready && (
        <div className="py-12 text-center font-mono text-xs uppercase tracking-[0.14em] text-ink-500 border border-dashed border-ink-700">
          {selected.length === 0
            ? "Select two submissions below to compare."
            : `${selected.length} of 2 selected - pick one more.`}
        </div>
      )}

      <div className="case-card crop-marks">
        <div className="px-4 py-3 border-b border-ink-700 flex flex-col sm:flex-row items-start sm:items-center gap-3">
          <div className="flex items-center gap-2 flex-1">
            <ArrowLeftRight className="w-4 h-4 text-ink-500 shrink-0" />
            <input
              type="text"
              placeholder="Search submissions..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 min-w-0 bg-transparent border-0 outline-none font-mono text-sm text-ink-100 placeholder:text-ink-600"
            />
          </div>
          <div className="flex items-center gap-3">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-ink-900 border border-ink-700 px-2 py-1 text-[11px] font-mono text-ink-300 focus:outline-none focus:border-iris transition"
            >
              <option value="date">Newest</option>
              <option value="score">Highest Score</option>
              <option value="verdict">Verdict</option>
              <option value="name">Name</option>
              <option value="size">Size</option>
            </select>
            {selected.length > 0 && (
              <button
                onClick={() => setSelected([])}
                className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-400 hover:text-ink-100 transition px-2 py-1 border border-ink-700 hover:border-ink-500"
              >
                Clear ({selected.length})
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-[1fr_100px_60px_70px_90px] gap-3 px-4 py-2.5 border-b border-ink-700 font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500">
          <span>File</span>
          <span>Date</span>
          <span>Size</span>
          <span className="text-right">Score</span>
          <span className="text-right">Action</span>
        </div>

        {sorted.map((sub) => {
          const isSelected = selected.includes(sub.id);
          const isDisabled = !isSelected && selected.length >= 2;
          const verdictCls = VERDICT_COLOR[sub.final_verdict] || VERDICT_COLOR.inconclusive;
          return (
            <div
              key={sub.id}
              className={clsx(
                "grid grid-cols-[1fr_100px_60px_70px_90px] gap-3 px-4 py-3 border-b border-ink-800 last:border-0 items-center transition-colors",
                isSelected && "bg-iris/5 border-l-2 border-l-iris",
                isDisabled && "opacity-40"
              )}
            >
              <div className="flex items-center gap-3 min-w-0">
                {sub.thumbnail_url ? (
                  <img
                    src={sub.thumbnail_url}
                    alt=""
                    className="w-8 h-8 object-cover border border-ink-700 shrink-0"
                    onError={(e) => {
                      const t = e.currentTarget;
                      t.style.display = "none";
                      const fb = t.nextElementSibling as HTMLElement | null;
                      if (fb) fb.style.display = "flex";
                    }}
                  />
                ) : null}
                <div
                  className="w-8 h-8 border border-ink-700 bg-ink-900 items-center justify-center font-mono text-[8px] text-ink-500 shrink-0"
                  style={{ display: sub.thumbnail_url ? "none" : "flex" }}
                >
                  {sub.mime_type?.split("/")[1]?.slice(0, 4).toUpperCase() || "FILE"}
                </div>
                <div className="min-w-0">
                  <div className="font-mono text-xs text-ink-100 truncate">{sub.original_filename}</div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className={clsx("badge border text-[9px] py-0", verdictCls)}>
                      {sub.final_verdict || sub.status}
                    </span>
                  </div>
                </div>
              </div>
              <span className="font-mono text-[10px] text-ink-400 ticker">
                {new Date(sub.created_at).toISOString().slice(0, 10)}
              </span>
              <span className="font-mono text-[10px] text-ink-400 ticker">{formatSize(sub.file_size)}</span>
              <span className={clsx("font-mono text-xs text-right ticker", verdictCls)}>
                {sub.final_score != null ? `${(sub.final_score * 100).toFixed(0)}%` : "-"}
              </span>
              <div className="flex justify-end">
                <button
                  onClick={() => !isDisabled && toggleSelect(sub.id)}
                  disabled={isDisabled}
                  className={clsx(
                    "font-mono text-[10px] uppercase tracking-[0.12em] px-2.5 py-1 border transition",
                    isSelected
                      ? "border-signal-blood/60 text-signal-blood hover:bg-signal-blood/10"
                      : "border-ink-700 text-ink-400 hover:border-iris hover:text-iris",
                    isDisabled && "cursor-not-allowed"
                  )}
                >
                  {isSelected ? "Remove" : "Compare"}
                </button>
              </div>
            </div>
          );
        })}

        {sorted.length === 0 && (
          <div className="py-12 text-center font-mono text-xs uppercase tracking-[0.14em] text-ink-500">
            No submissions found.
          </div>
        )}
      </div>

    </div>
  );
}

export default function ComparePage() {
  return <SubscriptionGate feature="Compare tool"><ComparePageInner /></SubscriptionGate>;
}
