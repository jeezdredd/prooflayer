import { useCallback, useState } from "react";
import DashboardFilters from "../components/DashboardFilters";
import SubmissionTable from "../components/SubmissionTable";
import { useDashboard } from "../hooks/useDashboard";

export default function DashboardPage() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);

  const params = { ...filters, page: String(page) };
  const { data, isLoading } = useDashboard(params);

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
