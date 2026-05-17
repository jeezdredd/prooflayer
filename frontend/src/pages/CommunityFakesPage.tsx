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
    <div className="animate-rise">
      <div className="mb-8 flex items-end justify-between flex-wrap gap-4">
        <div>
          <span className="label-mono signal-blood">Service / 04</span>
          <h1 className="font-display text-6xl text-ink-50 leading-none mt-3">
            Known <span className="italic text-signal-blood">Fakes</span>
          </h1>
          <p className="text-ink-400 mt-3 max-w-xl leading-relaxed">
            Submissions matching the community-curated registry of confirmed forgeries.
            Future uploads with the same SHA-256 are flagged automatically.
          </p>
        </div>
        {data && (
          <div className="text-right">
            <div className="font-display text-5xl text-signal-blood ticker">{data.count}</div>
            <div className="label-mono mt-1">Confirmed Fakes</div>
          </div>
        )}
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
