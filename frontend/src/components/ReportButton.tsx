import { useState } from "react";
import { useCreateReport } from "../hooks/useReports";

interface ReportButtonProps {
  submissionId: string;
}

const REASONS = [
  { value: "fake_content", label: "Fake content" },
  { value: "misleading", label: "Misleading" },
  { value: "copyright", label: "Copyright violation" },
  { value: "spam", label: "Spam" },
  { value: "other", label: "Other" },
];

export default function ReportButton({ submissionId }: ReportButtonProps) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("fake_content");
  const [description, setDescription] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const { mutate: createReport, isPending } = useCreateReport();

  function handleSubmit() {
    createReport(
      { submission: submissionId, reason, description },
      {
        onSuccess: () => {
          setSubmitted(true);
          setOpen(false);
        },
      }
    );
  }

  if (submitted) {
    return <span className="text-xs text-gray-400">Report submitted</span>;
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-xs text-gray-400 hover:text-red-500 transition-colors"
      >
        Report
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl p-6 w-full max-w-sm shadow-xl">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Report submission</h3>
            <div className="mb-3">
              <label className="text-xs text-gray-500 mb-1 block">Reason</label>
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              >
                {REASONS.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            <div className="mb-4">
              <label className="text-xs text-gray-500 mb-1 block">Details (optional)</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setOpen(false)}
                className="flex-1 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={isPending}
                className="flex-1 py-2 text-sm text-white bg-red-500 rounded-lg hover:bg-red-600 disabled:opacity-50"
              >
                Submit
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
