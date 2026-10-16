import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import UploadForm from "../components/UploadForm";
import UploadProgress from "../components/UploadProgress";
import { buildSteps } from "../components/AnalyzerTimeline";
import ResultCard from "../components/ResultCard";
import { useUploadFile, useSubmissionDetail } from "../hooks/useUpload";
import { useUploadStore } from "../stores/uploadStore";
import { useShaderStore } from "../stores/shaderStore";
import { toast } from "../components/ui/Toast";
import { batches, classrooms as classroomApi } from "../api/endpoints";
import { useQuery } from "@tanstack/react-query";
import { t, tn } from "../i18n";

export default function UploadPage() {
  const { status, progress, submissionId, reset } = useUploadStore();
  const triggerBoost = useShaderStore((s) => s.triggerBoost);
  const upload = useUploadFile();
  const { data: submission } = useSubmissionDetail(submissionId);
  const navigate = useNavigate();
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const isMountedRef = useRef(false);
  const [preview, setPreview] = useState<{ url: string; kind: "image" | "video" } | null>(null);

  useEffect(() => {
    if (!pendingFile) {
      setPreview(null);
      return;
    }
    const kind = pendingFile.type.startsWith("image/") ? "image" : pendingFile.type.startsWith("video/") ? "video" : null;
    if (!kind) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(pendingFile);
    setPreview({ url, kind });
    return () => URL.revokeObjectURL(url);
  }, [pendingFile]);

  const isComplete = submission?.status === "completed" || submission?.status === "failed";

  useEffect(() => {
    if (!isMountedRef.current) {
      isMountedRef.current = true;
      return;
    }
    if (submissionId && status === "processing") {
      navigate(`/results/${submissionId}`);
    }
  }, [submissionId, status, navigate]);

  const [batchUploading, setBatchUploading] = useState(false);
  const [classroom, setClassroom] = useState<string>("");
  const { data: myClasses = [] } = useQuery({
    queryKey: ["classrooms"],
    queryFn: () => classroomApi.list().then((r) => r.data),
    staleTime: 60_000,
  });
  const uploadTargets = myClasses.filter((c) => !c.archived);

  const handleBatchSelect = async (files: File[]) => {
    reset();
    triggerBoost();
    setBatchUploading(true);
    try {
      const res = await batches.create(files, "", classroom || null);
      const skipped = res.data.skipped.length;
      toast.success(tn(res.data.summary.total, "{n} file queued", "{n} files queued") + (skipped ? t(", {n} skipped", { n: skipped }) : ""));
      navigate(`/batches/${res.data.id}`);
    } catch (err: unknown) {
      const data = (err as { response?: { status?: number; data?: { code?: string; detail?: string; files?: string[] } } })?.response;
      if (data?.status === 402) toast.error(data.data?.detail ? t(data.data.detail) : t("Monthly limit reached"));
      else toast.error(data?.data?.files?.[0] ? t(data.data.files[0]) : t("Batch upload failed"));
    } finally {
      setBatchUploading(false);
    }
  };

  const handleFileSelect = (file: File) => {
    reset();
    setPendingFile(file);
    triggerBoost();
    upload.mutate({ file, classroom: classroom || null }, {
      onSuccess: () => toast.success(t("{name} uploaded", { name: file.name })),
      onError: () => toast.error(t("Upload failed")),
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
          {t("Service / 01")}
        </div>
        <h1 className="font-display text-[clamp(2.5rem,7vw,4.5rem)] text-ink-50 leading-[0.95] mt-4">
          {t("Verify")} <span className="italic text-iris">{t("Content")}</span>.
        </h1>
        <p className="text-ink-400 mt-4 max-w-xl leading-relaxed">
          {t("Submit image, video, audio, or text. Eleven analyzers run in parallel.")}
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
      >
        <UploadForm
          onFileSelect={handleFileSelect}
          onBatchSelect={handleBatchSelect}
          disabled={batchUploading || status === "uploading" || status === "processing"}
        />
        {uploadTargets.length > 0 && (
          <label className="mt-4 flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-400">
            {t("Submit to")}
            <select
              value={classroom}
              onChange={(e) => setClassroom(e.target.value)}
              className="bg-ink-950 border border-[var(--line-strong)] px-2 py-1 normal-case tracking-normal text-ink-100 focus:border-signal-amber outline-none"
            >
              <option value="">{t("my own checks")}</option>
              {uploadTargets.map((c) => (
                <option key={c.id} value={c.id}>
                  {t("class:")} {c.name}{c.role === "teacher" ? ` (${t("teacher")})` : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 mt-3">
          {batchUploading ? t("uploading batch…") : t("drop several files or a ZIP to check them as one batch (up to 100)")}
        </p>
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
              previewUrl={preview?.url}
              previewKind={preview?.kind}
              steps={submission ? buildSteps(submission) : undefined}
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
              <p className="font-mono text-sm text-signal-blood">{t("Upload failed")}</p>
              <p className="font-mono text-xs text-signal-blood/70 mt-1">{t("Check the file and try again.")}</p>
            </div>
            <button onClick={reset} className="btn-ghost shrink-0">
              {t("Reset")}
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
                {t("Verify another file")}
              </motion.button>
              <motion.button
                onClick={() => navigate(`/results/${submission.id}`)}
                className="btn-forensic"
                whileTap={{ scale: 0.97 }}
              >
                {t("View full result")} →
              </motion.button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
