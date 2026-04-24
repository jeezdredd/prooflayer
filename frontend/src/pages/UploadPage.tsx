import { useNavigate } from "react-router-dom";
import UploadForm from "../components/UploadForm";
import UploadProgress from "../components/UploadProgress";
import ResultCard from "../components/ResultCard";
import { useUploadFile, useSubmissionDetail } from "../hooks/useUpload";
import { useUploadStore } from "../stores/uploadStore";

export default function UploadPage() {
  const { status, progress, submissionId, reset } = useUploadStore();
  const upload = useUploadFile();
  const { data: submission } = useSubmissionDetail(submissionId);
  const navigate = useNavigate();

  const isComplete = submission?.status === "completed" || submission?.status === "failed";

  const handleFileSelect = (file: File) => {
    reset();
    upload.mutate(file);
  };

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Verify Content</h2>

      <UploadForm
        onFileSelect={handleFileSelect}
        disabled={status === "uploading" || status === "processing"}
      />

      {(status === "uploading" || (status === "processing" && !isComplete)) && (
        <UploadProgress
          progress={progress}
          status={status === "uploading" ? "uploading" : "processing"}
        />
      )}

      {status === "error" && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700">Upload failed. Please try again.</p>
          <button onClick={reset} className="mt-2 text-sm text-red-600 underline">
            Reset
          </button>
        </div>
      )}

      {isComplete && submission && (
        <div className="mt-6">
          <ResultCard submission={submission} />
          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={reset}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm"
            >
              Verify another file
            </button>
            <button
              onClick={() => navigate(`/results/${submission.id}`)}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
            >
              View full result →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
