import { useParams, Link } from "react-router-dom";
import { useSubmissionDetail } from "../hooks/useUpload";
import ResultCard from "../components/ResultCard";

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
      <Link to="/upload" className="text-sm text-blue-600 hover:underline mb-4 inline-block">
        &larr; Back to upload
      </Link>
      <ResultCard submission={submission} />
    </div>
  );
}
