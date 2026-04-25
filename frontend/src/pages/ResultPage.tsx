import { useParams, Link } from "react-router-dom";
import { useSubmissionDetail } from "../hooks/useUpload";
import ResultCard from "../components/ResultCard";
import VotingPanel from "../components/VotingPanel";
import ReportButton from "../components/ReportButton";
import ProvenancePanel from "../components/ProvenancePanel";

export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const { data: submission, isLoading, isError } = useSubmissionDetail(id || null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full" />
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
          <ReportButton submissionId={submission.id} />
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
