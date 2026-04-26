import { useCallback, useRef, useState } from "react";
import clsx from "clsx";

const ALLOWED_TYPES = [
  "image/jpeg", "image/png", "image/webp",
  "video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/webm",
  "audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", "audio/flac", "audio/mp4",
  "text/plain",
];

const MAX_SIZE = 500 * 1024 * 1024;

const FORMAT_GROUPS = [
  { label: "Image", formats: "JPEG, PNG, WebP" },
  { label: "Video", formats: "MP4, MOV, AVI, MKV, WebM" },
  { label: "Audio", formats: "MP3, WAV, OGG, FLAC" },
  { label: "Text", formats: "TXT" },
];

interface UploadFormProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
}

export default function UploadForm({ onFileSelect, disabled }: UploadFormProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndSubmit = useCallback(
    (file: File) => {
      setError(null);
      if (!ALLOWED_TYPES.includes(file.type)) {
        setError(`Unsupported file type: ${file.type || "unknown"}. See supported formats below.`);
        return;
      }
      if (file.size > MAX_SIZE) {
        setError("File too large. Maximum size is 500MB.");
        return;
      }
      onFileSelect(file);
    },
    [onFileSelect]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) validateAndSubmit(file);
    },
    [validateAndSubmit]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) validateAndSubmit(file);
    },
    [validateAndSubmit]
  );

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={clsx(
          "border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors",
          isDragging ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-gray-400",
          disabled && "opacity-50 pointer-events-none"
        )}
      >
        <div className="text-gray-500">
          <p className="text-lg font-medium text-gray-700">Drop your file here or click to browse</p>
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            {FORMAT_GROUPS.map(({ label, formats }) => (
              <span key={label} className="inline-flex items-center gap-1 text-xs bg-gray-100 rounded-md px-2 py-1">
                <span className="font-medium text-gray-600">{label}:</span>
                <span className="text-gray-500">{formats}</span>
              </span>
            ))}
          </div>
          <p className="mt-2 text-xs text-gray-400">Up to 500MB</p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.webp,.mp4,.mov,.avi,.mkv,.webm,.mp3,.wav,.ogg,.flac,.m4a,.txt"
          onChange={handleChange}
          className="hidden"
        />
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
