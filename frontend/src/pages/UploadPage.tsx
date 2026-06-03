import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import UploadForm from "../components/UploadForm";
import UploadProgress from "../components/UploadProgress";
import ResultCard from "../components/ResultCard";
import { useUploadFile, useSubmissionDetail } from "../hooks/useUpload";
import { useUploadStore } from "../stores/uploadStore";
import { useShaderStore } from "../stores/shaderStore";
import { toast } from "../components/ui/Toast";

export default function UploadPage() {
  const { status, progress, submissionId, reset } = useUploadStore();
  const triggerBoost = useShaderStore((s) => s.triggerBoost);
  const upload = useUploadFile();
  const { data: submission } = useSubmissionDetail(submissionId);
  const navigate = useNavigate();
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const isComplete = submission?.status === "completed" || submission?.status === "failed";

  useEffect(() => {
    if (submissionId && status === "processing") {
      navigate(`/results/${submissionId}`);
    }
  }, [submissionId, status, navigate]);

  const handleFileSelect = (file: File) => {
    reset();
    setPendingFile(file);
    triggerBoost();
    upload.mutate(file, {
      onSuccess: () => toast.success(`${file.name} uploaded`),
      onError: () => toast.error("Upload failed"),
    });
  };

  return (
    <div>
      <motion.div
        className="mb-10"
        initial={{ opacity: 0, y: 20, filter: "blur(8px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0)" }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="label-mono flex items-center gap-2">
          <span className="w-1.5 h-1.5 bg-signal-amber rounded-full pulse-dot" />
          Service / 01
        </div>
        <h1 className="font-display text-7xl text-ink-50 leading-[0.95] mt-4">
          Verify <span className="italic text-iris">Content</span>.
        </h1>
        <p className="text-ink-400 mt-4 max-w-xl leading-relaxed">
          Submit any image, video, audio, or text. Seven analyzers will examine in parallel and publish their evidence.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
      >
        <UploadForm
          onFileSelect={handleFileSelect}
          disabled={status === "uploading" || status === "processing"}
        />
      </motion.div>

      <AnimatePresence mode="wait">
        {(status === "uploading" || (status === "processing" && !isComplete)) && (
          <motion.div
            key="progress"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.5 }}
          >
            <UploadProgress
              progress={progress}
              status={status === "uploading" ? "uploading" : "processing"}
              statusMessage={submission?.status_message}
              filename={pendingFile?.name}
              fileSize={pendingFile?.size}
            />
          </motion.div>
        )}

        {status === "error" && (
          <motion.div
            key="error"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: [0, -8, 8, -8, 8, 0] }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
            className="mt-6 p-4 border border-signal-blood bg-signal-blood/5 flex items-start gap-3"
          >
            <div className="w-6 h-6 border border-signal-blood text-signal-blood text-xs font-bold flex items-center justify-center shrink-0">!</div>
            <div className="flex-1">
              <p className="font-mono text-sm text-signal-blood">Upload failed</p>
              <p className="font-mono text-xs text-signal-blood/70 mt-1">Check the file and try again.</p>
            </div>
            <button onClick={reset} className="btn-ghost shrink-0">
              Reset
            </button>
          </motion.div>
        )}

        {isComplete && submission && (
          <motion.div
            key="result"
            initial={{ opacity: 0, y: 30, filter: "blur(12px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0)" }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
            className="mt-8"
          >
            <ResultCard submission={submission} />
            <div className="mt-5 flex items-center gap-3">
              <motion.button
                onClick={reset}
                className="btn-ghost"
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.97 }}
              >
                Verify another file
              </motion.button>
              <motion.button
                onClick={() => navigate(`/results/${submission.id}`)}
                className="btn-forensic"
                whileTap={{ scale: 0.97 }}
              >
                View full result →
              </motion.button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
