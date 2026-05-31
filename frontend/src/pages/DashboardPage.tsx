import { useCallback, useState } from "react";
import DashboardFilters from "../components/DashboardFilters";
import SubmissionTable from "../components/SubmissionTable";
import { useDashboard, useDashboardStats } from "../hooks/useDashboard";

const VERDICT_COLORS: Record<string, string> = {
  authentic: "text-signal-sage",
  suspicious: "text-signal-amber",
  likely_fake: "text-signal-blood",
  fake: "text-signal-blood",
  needs_review: "text-signal-violet",
  inconclusive: "text-ink-300",
};

export default function DashboardPage() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);

  const params = { ...filters, page: String(page) };
  const { data, isLoading } = useDashboard(params);
  const { data: stats } = useDashboardStats();

  const handleFiltersChange = useCallback((newFilters: Record<string, string>) => {
    setFilters(newFilters);
    setPage(1);
  }, []);

  return (
    <div className="animate-rise">
      <div className="mb-8 flex items-end justify-between flex-wrap gap-4">
        <div>
          <span className="label-mono">Service / 02</span>
          <h1 className="font-display text-6xl text-ink-50 leading-none mt-3">
            Case <span className="italic text-signal-amber">Registry</span>
          </h1>
          <p className="text-ink-400 mt-3 max-w-xl leading-relaxed">
            All evidence files submitted under your clearance, with verdicts and forensic scores.
          </p>
        </div>
        {data && (
          <div className="text-right">
            <div className="font-display text-5xl text-ink-50 ticker">{data.count}</div>
            <div className="label-mono mt-1">Total Submissions</div>
          </div>
        )}
      </div>

      {stats && stats.total > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <div className="case-card p-4">
            <div className="label-mono">Avg Score</div>
            <div className="font-display text-3xl text-ink-50 ticker mt-1">
              {stats.avg_score !== null ? `${Math.round(stats.avg_score * 100)}%` : "-"}
            </div>
          </div>
          <div className="case-card p-4">
            <div className="label-mono">Known Fakes</div>
            <div className="font-display text-3xl text-signal-blood ticker mt-1">
              {stats.known_fake_hits}
            </div>
          </div>
          <div className="case-card p-4 col-span-2">
            <div className="label-mono mb-2">Verdict Breakdown</div>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {Object.entries(stats.by_verdict).map(([v, c]) => (
                <div key={v} className="flex items-center gap-1.5 font-mono text-xs">
                  <span className={VERDICT_COLORS[v] || "text-ink-300"}>{c}</span>
                  <span className="text-ink-500 uppercase tracking-wider text-[10px]">
                    {v.replace("_", " ")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <DashboardFilters onChange={handleFiltersChange} />
      <div className="mt-6">
        <SubmissionTable
          data={data}
          isLoading={isLoading}
          page={page}
          onPageChange={setPage}
        />
      </div>
    </div>
  );
}
