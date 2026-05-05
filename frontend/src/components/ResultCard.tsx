import clsx from "clsx";
import type { Submission } from "../types";
import AnalyzerTimeline from "./AnalyzerTimeline";

interface ResultCardProps {
  submission: Submission;
}

const VERDICT_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  authentic: { bg: "bg-green-100", text: "text-green-800", label: "Authentic" },
  suspicious: { bg: "bg-yellow-100", text: "text-yellow-800", label: "Suspicious" },
  likely_fake: { bg: "bg-orange-100", text: "text-orange-800", label: "Likely Fake" },
  fake: { bg: "bg-red-100", text: "text-red-800", label: "Fake" },
  needs_review: { bg: "bg-purple-100", text: "text-purple-800", label: "Needs Review" },
  inconclusive: { bg: "bg-gray-100", text: "text-gray-800", label: "Inconclusive" },
};

function getScoreColor(score: number): string {
  if (score < 0.3) return "text-green-600";
  if (score < 0.5) return "text-yellow-600";
  if (score < 0.7) return "text-orange-600";
  return "text-red-600";
}

export default function ResultCard({ submission }: ResultCardProps) {
  const verdict = VERDICT_STYLES[submission.final_verdict] || VERDICT_STYLES.inconclusive;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{submission.original_filename}</h3>
          <p className="text-sm text-gray-500 mt-1">
            {submission.mime_type} &middot; {(submission.file_size / 1024).toFixed(0)} KB
          </p>
        </div>
        <span className={clsx("px-3 py-1 rounded-full text-sm font-medium", verdict.bg, verdict.text)}>
          {verdict.label}
        </span>
      </div>

      {submission.final_score !== null && (
        <div className="mb-6">
          <div className="flex items-baseline gap-2">
            <span className={clsx("text-4xl font-bold", getScoreColor(submission.final_score))}>
              {(submission.final_score * 100).toFixed(0)}%
            </span>
            <span className="text-sm text-gray-500">fake probability</span>
          </div>
          <div className="mt-2 w-full bg-gray-200 rounded-full h-3">
            <div
              className={clsx("h-3 rounded-full", {
                "bg-green-500": submission.final_score < 0.3,
                "bg-yellow-500": submission.final_score >= 0.3 && submission.final_score < 0.5,
                "bg-orange-500": submission.final_score >= 0.5 && submission.final_score < 0.7,
                "bg-red-500": submission.final_score >= 0.7,
              })}
              style={{ width: `${submission.final_score * 100}%` }}
            />
          </div>
        </div>
      )}

      {submission.is_known_fake && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700 font-medium">
            This file matches a known fake in our database.
          </p>
        </div>
      )}

      <AnalyzerTimeline submission={submission} />
    </div>
  );
}
