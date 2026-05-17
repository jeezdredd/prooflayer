import { useCallback, useRef, useState } from "react";
import clsx from "clsx";
import { motion } from "motion/react";
import { UploadCloud, Image, Film, AudioLines, FileText } from "lucide-react";

const ALLOWED_TYPES = [
  "image/jpeg", "image/png", "image/webp",
  "video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/webm",
  "audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", "audio/flac", "audio/mp4",
  "text/plain",
];

const MAX_SIZE = 500 * 1024 * 1024;

const FORMAT_GROUPS = [
  { label: "Image", formats: ["JPEG", "PNG", "WEBP"], color: "text-signal-cyan", Icon: Image },
  { label: "Video", formats: ["MP4", "MOV", "MKV", "WEBM"], color: "text-signal-amber", Icon: Film },
  { label: "Audio", formats: ["MP3", "WAV", "OGG", "FLAC"], color: "text-signal-violet", Icon: AudioLines },
  { label: "Text", formats: ["TXT"], color: "text-signal-sage", Icon: FileText },
];

interface UploadFormProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
}

export default function UploadForm({ onFileSelect, disabled }: UploadFormProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [hoverGroup, setHoverGroup] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndSubmit = useCallback(
    (file: File) => {
      setError(null);
      if (!ALLOWED_TYPES.includes(file.type)) {
        setError(`Unsupported MIME type: ${file.type || "unknown"}`);
        return;
      }
      if (file.size > MAX_SIZE) {
        setError("File exceeds 500 MB limit.");
        return;
      }
      onFileSelect(file);
    },
    [onFileSelect],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) validateAndSubmit(file);
    },
    [validateAndSubmit],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) validateAndSubmit(file);
    },
    [validateAndSubmit],
  );

  return (
    <div className="space-y-3">
      {/* DROPZONE */}
      <motion.div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        whileHover={!disabled ? { scale: 1.005 } : undefined}
        className={clsx(
          "relative cursor-pointer rounded-md transition-all duration-300 overflow-hidden",
          isDragging
            ? "ring-2 ring-signal-amber bg-signal-amber/[0.06]"
            : "ring-1 ring-white/10 hover:ring-signal-amber/40 bg-ink-900/40",
          "backdrop-blur-xl",
          disabled && "opacity-40 pointer-events-none",
        )}
      >
        {/* glow accent on drag */}
        {isDragging && (
          <motion.div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                "radial-gradient(ellipse 60% 50% at 50% 50%, rgba(245,176,66,0.15), transparent 70%)",
            }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          />
        )}

        <div className="px-8 py-16 lg:py-20 flex flex-col items-center text-center relative">
          <motion.div
            animate={
              isDragging
                ? { y: [-2, -8, -2], transition: { duration: 1.4, repeat: Infinity, ease: "easeInOut" } }
                : { y: 0 }
            }
            className={clsx(
              "mb-6 w-16 h-16 rounded-full flex items-center justify-center transition-colors",
              isDragging
                ? "bg-signal-amber/15 text-signal-amber ring-1 ring-signal-amber/40"
                : "bg-white/[0.04] text-ink-300 ring-1 ring-white/10",
            )}
          >
            <UploadCloud size={28} strokeWidth={1.4} />
          </motion.div>

          <h3 className="font-display text-3xl lg:text-4xl text-ink-50 leading-tight">
            {isDragging ? (
              <>Release to <span className="italic text-signal-amber">submit</span></>
            ) : (
              <>Drop file here or <span className="italic text-iris">click to browse</span></>
            )}
          </h3>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-500 mt-3">
            Max 500 MB · End-to-end JWT
          </p>

          {/* Format chips inline - hover reveals supported list */}
          <div className="mt-7 flex flex-wrap items-center justify-center gap-2">
            {FORMAT_GROUPS.map(({ label, formats, color, Icon }) => (
              <div
                key={label}
                onMouseEnter={() => setHoverGroup(label)}
                onMouseLeave={() => setHoverGroup(null)}
                onClick={(e) => e.stopPropagation()}
                className="relative group"
              >
                <span
                  className={clsx(
                    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] ring-1 ring-white/8 hover:ring-white/20 transition-colors font-mono text-[10px] uppercase tracking-[0.14em]",
                    color,
                  )}
                >
                  <Icon size={11} strokeWidth={2} />
                  {label}
                </span>
                {hoverGroup === label && (
                  <motion.span
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.15 }}
                    className="absolute left-1/2 -translate-x-1/2 top-full mt-1.5 px-2.5 py-1.5 bg-ink-950 border border-white/10 rounded-sm font-mono text-[10px] uppercase tracking-[0.12em] text-ink-200 whitespace-nowrap z-20 shadow-lg pointer-events-none"
                  >
                    {formats.join(" · ")}
                    <span className="absolute left-1/2 -translate-x-1/2 -top-1 w-2 h-2 bg-ink-950 border-l border-t border-white/10 rotate-45" />
                  </motion.span>
                )}
              </div>
            ))}
          </div>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.webp,.mp4,.mov,.avi,.mkv,.webm,.mp3,.wav,.ogg,.flac,.m4a,.txt"
          onChange={handleChange}
          className="hidden"
        />
      </motion.div>

      {error && (
        <motion.div
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: [0, -6, 6, -4, 4, 0] }}
          transition={{ duration: 0.45 }}
          className="flex items-center gap-3 px-4 py-3 rounded-sm border border-signal-blood/40 bg-signal-blood/5"
        >
          <span className="w-5 h-5 border border-signal-blood text-signal-blood text-[10px] font-bold flex items-center justify-center rounded-full">!</span>
          <span className="font-mono text-xs text-signal-blood">{error}</span>
        </motion.div>
      )}
    </div>
  );
}
