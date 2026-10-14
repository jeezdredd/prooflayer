import { useState } from "react";
import { useParams, Link, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useSubmissionDetail } from "../hooks/useUpload";
import { useSubmissionWS } from "../hooks/useSubmissionWS";
import ResultCard from "../components/ResultCard";
import VotingPanel from "../components/VotingPanel";
import ReportButton from "../components/ReportButton";
import ProvenancePanel from "../components/ProvenancePanel";
import ObjectionPanel from "../components/ObjectionPanel";
import { Skeleton, SkeletonText } from "../components/ui/Skeleton";
import { toast } from "../components/ui/Toast";
import { reanalyzeSubmission, togglePublic } from "../api/endpoints";
import { IS_CLASSROOM_APP } from "../appMode";
import { useAuthStore } from "../stores/authStore";
import type { Submission } from "../types";

function DownloadReportButton({ submissionId }: { submissionId: string }) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      const { getAccessToken } = await import("../api/client");
      const access = getAccessToken();
      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/content/submissions/${submissionId}/report.pdf`,
        {
          headers: access ? { Authorization: `Bearer ${access}` } : {},
          credentials: "include",
        }
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
      className="font-mono text-[10px] uppercase tracking-[0.14em] border border-iris/60 text-iris hover:bg-iris/10 px-3 py-1.5 transition disabled:opacity-50 flex items-center gap-1.5"
    >
      {loading ? "…" : "↓"} PDF Report
    </button>
  );
}

function ReanalyzeButton({ submissionId }: { submissionId: string }) {
  const [loading, setLoading] = useState(false);
  const queryClient = useQueryClient();

  const handleClick = async () => {
    setLoading(true);
    try {
      await reanalyzeSubmission(submissionId);
      await queryClient.invalidateQueries({ queryKey: ["submission", submissionId] });
      toast.success("Re-analyzing with the current Tribunal");
    } catch (err: unknown) {
      const code = (err as { response?: { data?: { code?: string } } })?.response?.data?.code;
      toast.error(code === "upload_limit_reached" ? "Monthly limit reached" : "Could not start re-analysis");
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className="font-mono text-[10px] uppercase tracking-[0.14em] border border-signal-amber/40 text-signal-amber px-3 py-1.5 transition hover:bg-signal-amber/10 disabled:opacity-50"
    >
      {loading ? "…" : "↻"} Re-analyze
    </button>
  );
}

function TogglePublicButton({ submissionId, isPublic }: { submissionId: string; isPublic: boolean }) {
  const [loading, setLoading] = useState(false);
  const [sensitive, setSensitive] = useState(false);
  const [adultRequired, setAdultRequired] = useState(false);
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const canPublish = !!(user?.is_adult || user?.is_staff) && !adultRequired;

  const handleToggle = async () => {
    setLoading(true);
    try {
      const res = await togglePublic(submissionId, !isPublic && sensitive);
      queryClient.setQueryData(["submission", submissionId], (old: Submission | undefined) =>
        old ? { ...old, is_public: res.data.is_public, is_sensitive: res.data.is_sensitive } : old
      );
      toast.success(res.data.is_public ? "Submission is now public" : "Submission set to private");
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { code?: string; detail?: string } } })?.response?.data;
      if (data?.code === "adult_required") setAdultRequired(true);
      toast.error(data?.detail || "Failed to update visibility");
    } finally {
      setLoading(false);
    }
  };

  if (!isPublic && !canPublish) return null;

  return (
    <div className="flex items-center gap-2">
      {!isPublic && (
        <label className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 cursor-pointer">
          <input type="checkbox" checked={sensitive} onChange={(e) => setSensitive(e.target.checked)} />
          Contains sensitive content
        </label>
      )}
      <button
        onClick={handleToggle}
        disabled={loading}
        title={isPublic ? "Make private" : "Publish to the public feed"}
        className={`font-mono text-[10px] uppercase tracking-[0.14em] border px-3 py-1.5 transition disabled:opacity-50 flex items-center gap-1.5 ${
          isPublic
            ? "border-signal-sage/60 text-signal-sage hover:bg-signal-sage/10"
            : "border-ink-600 text-ink-400 hover:border-ink-400 hover:text-ink-200"
        }`}
      >
        {loading ? "..." : isPublic ? "⬤ Public" : "○ Private"}
      </button>
    </div>
  );
}

export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const { data: submission, isLoading, isError } = useSubmissionDetail(id || null);
  const { connected, runningAnalyzers } = useSubmissionWS(id);
  const location = useLocation();
  const supervising = !!(location.state as { supervising?: boolean } | null)?.supervising;
  const student = !!useAuthStore((s) => s.user?.student_only);

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
        <div className="case-card p-6 space-y-4">
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
          <div className="space-y-3 pt-4 border-t border-ink-800">
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
        <p className="text-ink-400 font-mono text-sm">Submission not found.</p>
        <Link to={IS_CLASSROOM_APP ? "/" : "/upload"} className="mt-2 inline-block text-iris hover:text-iris-light underline text-sm">
          {IS_CLASSROOM_APP ? "Back to your classes" : "Go back to upload"}
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.14em]">
          {IS_CLASSROOM_APP ? (
            <Link to="/" className="text-ink-400 hover:text-ink-100 transition">
              &larr; Classes
            </Link>
          ) : (
            <>
              <Link to="/dashboard" className="text-ink-400 hover:text-ink-100 transition">
                &larr; Dashboard
              </Link>
              <span className="text-ink-700">/</span>
              <Link to="/upload" className="text-iris hover:text-iris-light transition">
                Verify another
              </Link>
            </>
          )}
        </div>
        {submission.status === "processing" && connected && (
          <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-signal-sage">
            <span className="w-1.5 h-1.5 rounded-full bg-signal-sage pulse-dot" />
            Live
          </span>
        )}
        {submission.status === "completed" && (
          <div className="flex items-center gap-2">
            {!student && submission.ensemble && !submission.ensemble.is_current && (
              <ReanalyzeButton submissionId={submission.id} />
            )}
            {!supervising && !student && <TogglePublicButton submissionId={submission.id} isPublic={submission.is_public} />}
            <DownloadReportButton submissionId={submission.id} />
            <ReportButton submissionId={submission.id} />
          </div>
        )}
      </div>
      <ResultCard submission={submission} runningAnalyzers={runningAnalyzers} />
      <ObjectionPanel submission={submission} supervising={supervising} />
      {submission.status === "completed" && (
        <ProvenancePanel submissionId={submission.id} />
      )}
      {submission.status === "completed" && !student && (
        <VotingPanel submissionId={submission.id} fileUrl={submission.file_url} />
      )}
    </div>
  );
}
