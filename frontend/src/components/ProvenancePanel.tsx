import { useProvenance } from "../hooks/useProvenance";

const SOURCE_LABELS: Record<string, string> = {
  phash_match: "Similar in DB",
  tineye: "TinEye",
  google_vision: "Google Vision",
  c2pa: "C2PA Credentials",
};

const SOURCE_COLORS: Record<string, string> = {
  phash_match: "bg-blue-50 text-blue-700 border-blue-200",
  tineye: "bg-purple-50 text-purple-700 border-purple-200",
  google_vision: "bg-indigo-50 text-indigo-700 border-indigo-200",
  c2pa: "bg-green-50 text-green-700 border-green-200",
};

interface ProvenancePanelProps {
  submissionId: string;
}

export default function ProvenancePanel({ submissionId }: ProvenancePanelProps) {
  const { data: results, isLoading } = useProvenance(submissionId);

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 mt-4">
        <h4 className="text-sm font-semibold text-gray-700 mb-3">Provenance</h4>
        <p className="text-sm text-gray-400">Checking sources...</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 mt-4">
      <h4 className="text-sm font-semibold text-gray-700 mb-3">Provenance</h4>

      {!results || results.length === 0 ? (
        <p className="text-sm text-gray-400">No matches found in external sources.</p>
      ) : (
        <div className="space-y-3">
          {results.map((r) => (
            <div key={r.id} className="flex items-start justify-between gap-3 p-3 bg-gray-50 rounded-lg">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full border font-medium ${SOURCE_COLORS[r.source_type] ?? "bg-gray-100 text-gray-600 border-gray-200"}`}
                  >
                    {SOURCE_LABELS[r.source_type] ?? r.source_type}
                  </span>
                  {r.similarity_score !== null && (
                    <span className="text-xs text-gray-500">
                      {(r.similarity_score * 100).toFixed(0)}% match
                    </span>
                  )}
                </div>
                {r.title && (
                  <p className="text-sm text-gray-700 truncate">{r.title}</p>
                )}
                {r.source_url && (
                  <a
                    href={r.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 hover:underline truncate block"
                  >
                    {r.source_url}
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
