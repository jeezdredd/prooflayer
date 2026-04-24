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
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Your submission history</p>
      </div>
      <DashboardFilters onChange={handleFiltersChange} />
      <SubmissionTable
        data={data}
        isLoading={isLoading}
        page={page}
        onPageChange={setPage}
      />
    </div>
  );
}
