import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useSubmissionDetail } from "../hooks/useUpload";
import ResultCard from "../components/ResultCard";
import VotingPanel from "../components/VotingPanel";
import ReportButton from "../components/ReportButton";
import ProvenancePanel from "../components/ProvenancePanel";
import { Skeleton, SkeletonText } from "../components/ui/Skeleton";
import { toast } from "../components/ui/Toast";

function DownloadReportButton({ submissionId }: { submissionId: string }) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      const tokens = localStorage.getItem("tokens");
      const access = tokens ? JSON.parse(tokens).access : null;
      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/content/submissions/${submissionId}/report.pdf`,
        { headers: access ? { Authorization: `Bearer ${access}` } : {} }
      );
      if (!res.ok) throw new Error("Failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `prooflayer_report_${submissionId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Report downloaded");
    } catch {
      toast.error("Failed to download report");
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1.5"
    >
      {loading ? "…" : "↓"} PDF Report
    </button>
  );
}

export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const { data: submission, isLoading, isError } = useSubmissionDetail(id || null);

  if (isLoading) {
    return (
      <div className="animate-fade-in">
        <div className="flex items-center justify-between mb-4">
          <Skeleton className="h-4 w-48" />
          <div className="flex gap-2">
            <Skeleton className="h-8 w-32 rounded-lg" />
            <Skeleton className="h-8 w-24 rounded-lg" />
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <div className="flex items-start justify-between">
            <div className="space-y-2 flex-1">
              <Skeleton className="h-5 w-2/5" />
              <Skeleton className="h-3 w-1/4" />
            </div>
            <Skeleton className="h-7 w-24 rounded-full" />
          </div>
          <div className="flex items-center gap-3">
            <Skeleton className="w-32 h-32 rounded" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
              <Skeleton className="h-3 w-3/4" />
            </div>
          </div>
          <div className="space-y-3 pt-4 border-t border-gray-100">
            <Skeleton className="h-4 w-1/3" />
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-3 pl-10">
                <Skeleton className="w-8 h-8 rounded-full" />
                <div className="flex-1">
                  <SkeletonText lines={1} />
                </div>
                <Skeleton className="h-5 w-20 rounded-full" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (isError || !submission) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500">Submission not found.</p>
        <Link to="/upload" className="mt-2 text-blue-600 hover:underline text-sm">
          Go back to upload
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Link to="/dashboard" className="text-sm text-gray-500 hover:text-gray-700">
            &larr; Dashboard
          </Link>
          <span className="text-gray-300">/</span>
          <Link to="/upload" className="text-sm text-blue-600 hover:underline">
            Verify another
          </Link>
        </div>
        {submission.status === "completed" && (
          <div className="flex items-center gap-2">
            <DownloadReportButton submissionId={submission.id} />
            <ReportButton submissionId={submission.id} />
          </div>
        )}
      </div>
      <ResultCard submission={submission} />
      {submission.status === "completed" && (
        <ProvenancePanel submissionId={submission.id} />
      )}
      {submission.status === "completed" && (
        <VotingPanel submissionId={submission.id} fileUrl={submission.file_url} />
      )}
    </div>
  );
}
