import clsx from "clsx";

interface UploadProgressProps {
  progress: number;
  status: "uploading" | "processing";
}

export default function UploadProgress({ progress, status }: UploadProgressProps) {
  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">
          {status === "uploading" ? "Uploading..." : "Analyzing..."}
        </span>
        <span className="text-sm text-gray-500">
          {status === "uploading" ? `${progress}%` : "Please wait"}
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={clsx(
            "h-2 rounded-full transition-all duration-300",
            status === "uploading" ? "bg-blue-600" : "bg-yellow-500 animate-pulse"
          )}
          style={{ width: status === "uploading" ? `${progress}%` : "100%" }}
        />
      </div>
    </div>
  );
}
