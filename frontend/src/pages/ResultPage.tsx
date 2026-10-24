import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useSubmissionDetail } from "../hooks/useUpload";
import { useSubmissionWS } from "../hooks/useSubmissionWS";
import ResultCard from "../components/ResultCard";
import VotingPanel from "../components/VotingPanel";
import ReportButton from "../components/ReportButton";
import ProvenancePanel from "../components/ProvenancePanel";
import ObjectionPanel from "../components/ObjectionPanel";
import ObjectionBanner from "../components/ObjectionBanner";
import { isClassView, isImage, isStudentView } from "../components/resultView";
import { Skeleton, SkeletonText } from "../components/ui/Skeleton";
import { toast } from "../components/ui/Toast";
import { getAccessToken } from "../api/client";
import { reanalyzeSubmission, togglePublic } from "../api/endpoints";
import { IS_CLASSROOM_APP } from "../appMode";
import { classPath } from "../classroom/shared";
import { LEGAL } from "../legal";
import { useAuthStore } from "../stores/authStore";
import type { Submission } from "../types";
import { t } from "../i18n";

function reportErrorText(status: number, code: string | undefined, student: boolean): string {
  if (status === 402 && code === "school_plan_required") {
    return student
      ? t("Your school's plan does not include PDF reports. The whole result is on this page.")
      : t("PDF reports for class work come with the school plan.");
  }
  if (status === 402) return t("PDF reports require Pro subscription.");
  return t("Failed to download report");
}

function DownloadReportButton({ submissionId, student }: { submissionId: string; student: boolean }) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      const access = getAccessToken();
      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/content/submissions/${submissionId}/report.pdf`,
        {
          headers: access ? { Authorization: `Bearer ${access}` } : {},
          credentials: "include",
        }
      );
      if (!res.ok) {
        const data = (await res.json().catch(() => null)) as { code?: string } | null;
        toast.error(reportErrorText(res.status, data?.code, student));
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `prooflayer_report_${submissionId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(t("Report downloaded"));
    } catch {
      toast.error(t("Failed to download report"));
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
      {loading ? "…" : "↓"} {t("PDF Report")}
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
      toast.success(t("Re-analyzing with the current Tribunal"));
    } catch (err: unknown) {
      const code = (err as { response?: { data?: { code?: string } } })?.response?.data?.code;
      toast.error(code === "upload_limit_reached" ? t("Monthly limit reached") : t("Could not start re-analysis"));
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
      {loading ? "…" : "↻"} {t("Re-analyze")}
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
      toast.success(res.data.is_public ? t("Submission is now public") : t("Submission set to private"));
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { code?: string; detail?: string } } })?.response?.data;
      if (data?.code === "adult_required") setAdultRequired(true);
      toast.error(data?.detail ? t(data.detail) : t("Failed to update visibility"));
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
          {t("Contains sensitive content")}
        </label>
      )}
      <button
        onClick={handleToggle}
        disabled={loading}
        title={isPublic ? t("Make private") : t("Publish to the public feed")}
        className={`font-mono text-[10px] uppercase tracking-[0.14em] border px-3 py-1.5 transition disabled:opacity-50 flex items-center gap-1.5 ${
          isPublic
            ? "border-signal-sage/60 text-signal-sage hover:bg-signal-sage/10"
            : "border-ink-600 text-ink-400 hover:border-ink-400 hover:text-ink-200"
        }`}
      >
        {loading ? "..." : isPublic ? `⬤ ${t("Public")}` : `○ ${t("Private")}`}
      </button>
    </div>
  );
}

function BackLinks({ submission }: { submission: Submission }) {
  if (IS_CLASSROOM_APP) {
    const target = submission.classroom;
    return (
      <Link to={target ? classPath(target) : "/"} className="text-ink-400 hover:text-ink-100 transition normal-case tracking-normal text-sm">
        &larr; {target ? target.name : t("Classes")}
      </Link>
    );
  }
  return (
    <>
      <Link to="/dashboard" className="text-ink-400 hover:text-ink-100 transition">
        &larr; {t("Dashboard")}
      </Link>
      <span className="text-ink-700">/</span>
      <Link to="/upload" className="text-iris hover:text-iris-light transition">
        {t("Verify another")}
      </Link>
    </>
  );
}

export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const { data: submission, isLoading, isError } = useSubmissionDetail(id || null);
  const { connected, runningAnalyzers } = useSubmissionWS(id);

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
        <p className="text-ink-400 font-mono text-sm">{t("Submission not found.")}</p>
        <Link to={IS_CLASSROOM_APP ? "/" : "/upload"} className="mt-2 inline-block text-iris hover:text-iris-light underline text-sm">
          {IS_CLASSROOM_APP ? t("Back to your classes") : t("Go back to upload")}
        </Link>
      </div>
    );
  }

  const student = isStudentView(submission);
  const classView = isClassView(submission);
  const completed = submission.status === "completed";

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.14em]">
          <BackLinks submission={submission} />
        </div>
        {submission.status === "processing" && connected && (
          <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-signal-sage">
            <span className="w-1.5 h-1.5 rounded-full bg-signal-sage pulse-dot" />
            {t("Live")}
          </span>
        )}
        {completed && (
          <div className="flex flex-wrap items-center gap-2">
            {!student && submission.ensemble && !submission.ensemble.is_current && (
              <ReanalyzeButton submissionId={submission.id} />
            )}
            {!IS_CLASSROOM_APP && submission.can_publish && (
              <TogglePublicButton submissionId={submission.id} isPublic={submission.is_public} />
            )}
            <DownloadReportButton submissionId={submission.id} student={student} />
            {!classView && <ReportButton submissionId={submission.id} />}
          </div>
        )}
      </div>
      <ObjectionBanner submission={submission} />
      <ResultCard submission={submission} runningAnalyzers={runningAnalyzers} />
      <ObjectionPanel submission={submission} />
      {completed && isImage(submission) && <ProvenancePanel submission={submission} />}
      {completed && !student && !classView && (
        <VotingPanel submissionId={submission.id} fileUrl={submission.file_url} />
      )}
      {completed && classView && !student && (
        <p className="mt-4 text-xs text-ink-500">
          {t("Think the check got it wrong?")}{" "}
          <a href={`mailto:${LEGAL.emails.support}`} className="text-ink-300 underline hover:text-ink-100">
            {t("Write to us")}
          </a>
        </p>
      )}
    </div>
  );
}
