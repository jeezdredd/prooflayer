import { useState } from "react";
import { useCreateReport } from "../hooks/useReports";
import { msg, t } from "../i18n";

interface ReportButtonProps {
  submissionId: string;
}

const REASONS = [
  { value: "fake_content", label: msg("Fake content") },
  { value: "misleading", label: msg("Misleading") },
  { value: "copyright", label: msg("Copyright violation") },
  { value: "adult_content", label: msg("Adult or sensitive content") },
  { value: "spam", label: msg("Spam") },
  { value: "other", label: msg("Other") },
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
    return <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">{t("Report submitted")}</span>;
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="font-mono text-[10px] uppercase tracking-[0.14em] border border-ink-700 text-ink-400 hover:border-signal-blood hover:text-signal-blood px-3 py-1.5 transition"
      >
        {t("Report")}
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="case-card crop-marks p-6 w-full max-w-sm">
            <h3 className="font-display text-xl text-white mb-4">{t("Report submission")}</h3>
            <div className="mb-3">
              <label className="label-mono block mb-1">{t("Reason")}</label>
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full border border-ink-700 px-3 py-2 text-sm font-mono text-ink-100 focus:outline-none focus:border-iris transition appearance-none"
                style={{ background: "var(--ink-900, #0d0f14)", colorScheme: "dark" }}
              >
                {REASONS.map((r) => (
                  <option key={r.value} value={r.value}>{t(r.label)}</option>
                ))}
              </select>
            </div>
            <div className="mb-4">
              <label className="label-mono block mb-1">{t("Details (optional)")}</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="w-full border border-ink-700 px-3 py-2 text-sm font-mono text-ink-100 resize-none focus:outline-none focus:border-iris transition placeholder:text-ink-500 appearance-none"
                style={{ background: "var(--ink-900, #0d0f14)", colorScheme: "dark" }}
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setOpen(false)}
                className="flex-1 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-300 border border-ink-700 hover:bg-ink-800 transition"
              >
                {t("Cancel")}
              </button>
              <button
                onClick={handleSubmit}
                disabled={isPending}
                className="flex-1 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-signal-blood border border-signal-blood/60 hover:bg-signal-blood/10 disabled:opacity-50 transition"
              >
                {t("Submit")}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
