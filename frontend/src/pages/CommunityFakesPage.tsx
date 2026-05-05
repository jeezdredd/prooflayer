import { useState } from "react";
import SubmissionTable from "../components/SubmissionTable";
import { useDashboard } from "../hooks/useDashboard";

export default function CommunityFakesPage() {
  const [page, setPage] = useState(1);

  const params: Record<string, string> = {
    is_known_fake: "true",
    ordering: "-created_at",
    page: String(page),
  };
  const { data, isLoading } = useDashboard(params);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Community Fakes</h1>
        <p className="text-sm text-gray-500 mt-1">
          Confirmed fake submissions flagged by the community or matching the known-fake database.
        </p>
      </div>
      <SubmissionTable
        data={data}
        isLoading={isLoading}
        page={page}
        onPageChange={setPage}
      />
    </div>
  );
}
