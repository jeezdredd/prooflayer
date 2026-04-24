import { useEffect, useState } from "react";

interface Filters {
  search?: string;
  status?: string;
  final_verdict?: string;
}

interface DashboardFiltersProps {
  onChange: (filters: Record<string, string>) => void;
}

const VERDICTS = ["", "authentic", "suspicious", "likely_fake", "fake", "needs_review", "inconclusive"];
const STATUSES = ["", "pending", "processing", "completed", "failed"];

export default function DashboardFilters({ onChange }: DashboardFiltersProps) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [verdict, setVerdict] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      const params: Record<string, string> = {};
      if (search) params.search = search;
      if (status) params.status = status;
      if (verdict) params.final_verdict = verdict;
      onChange(params);
    }, 300);
    return () => clearTimeout(timer);
  }, [search, status, verdict, onChange]);

  function handleClear() {
    setSearch("");
    setStatus("");
    setVerdict("");
  }

  const hasFilters = search || status || verdict;

  return (
    <div className="flex flex-wrap gap-3 mb-6">
      <input
        type="text"
        placeholder="Search by filename..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-60 focus:outline-none focus:ring-1 focus:ring-gray-300"
      />
      <select
        value={status}
        onChange={(e) => setStatus(e.target.value)}
        className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
      >
        <option value="">All statuses</option>
        {STATUSES.filter(Boolean).map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
      <select
        value={verdict}
        onChange={(e) => setVerdict(e.target.value)}
        className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
      >
        <option value="">All verdicts</option>
        {VERDICTS.filter(Boolean).map((v) => (
          <option key={v} value={v}>{v.replace("_", " ")}</option>
        ))}
      </select>
      {hasFilters && (
        <button
          onClick={handleClear}
          className="text-sm text-gray-400 hover:text-gray-600"
        >
          Clear
        </button>
      )}
    </div>
  );
}
