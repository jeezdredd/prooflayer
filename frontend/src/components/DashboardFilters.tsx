import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";

interface DashboardFiltersProps {
  onChange: (filters: Record<string, string>) => void;
}

const VERDICTS = ["authentic", "suspicious", "likely_fake", "fake", "needs_review", "inconclusive"];
const STATUSES = ["pending", "processing", "completed", "failed"];

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
    <div className="flex flex-wrap items-center gap-3 mb-6">
      <div className="relative flex-1 min-w-[240px] max-w-sm">
        <Search size={14} strokeWidth={1.5} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-500 pointer-events-none" />
        <input
          type="search"
          placeholder="Search by filename…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input-forensic pl-9"
        />
      </div>
      <select
        value={status}
        onChange={(e) => setStatus(e.target.value)}
        className="input-forensic w-40 cursor-pointer"
      >
        <option value="">All statuses</option>
        {STATUSES.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
      <select
        value={verdict}
        onChange={(e) => setVerdict(e.target.value)}
        className="input-forensic w-44 cursor-pointer"
      >
        <option value="">All verdicts</option>
        {VERDICTS.map((v) => (
          <option key={v} value={v}>{v.replace("_", " ")}</option>
        ))}
      </select>
      {hasFilters && (
        <button
          onClick={handleClear}
          className="flex items-center gap-1.5 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-400 hover:text-signal-blood transition-colors"
        >
          <X size={12} strokeWidth={2} />
          Clear
        </button>
      )}
    </div>
  );
}
