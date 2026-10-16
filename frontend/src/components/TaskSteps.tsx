import clsx from "clsx";
import { motion } from "motion/react";
import { t } from "../i18n";
import { ANALYZER_LABELS, type Step } from "./AnalyzerTimeline";

function Marker({ state }: { state: Step["state"] }) {
  if (state === "done") {
    return (
      <span className="w-[18px] h-[18px] rounded-full border border-signal-violet/50 bg-signal-violet/10 text-signal-violet flex items-center justify-center shrink-0">
        <svg viewBox="0 0 18 18" className="check-draw w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4.5 9.5l3 3 6-7" />
        </svg>
      </span>
    );
  }
  if (state === "running") {
    return <span className="w-[18px] h-[18px] rounded-full border-2 border-signal-amber/25 border-t-signal-amber animate-spin shrink-0" />;
  }
  if (state === "skipped") {
    return <span className="w-[18px] h-[18px] rounded-full border border-ink-700 text-ink-500 text-[11px] leading-none flex items-center justify-center shrink-0">×</span>;
  }
  return <span className="w-[18px] h-[18px] rounded-full border border-dashed border-ink-600 shrink-0" />;
}

export default function TaskSteps({ steps }: { steps: Step[] }) {
  const done = steps.filter((s) => s.state === "done").length;
  return (
    <div className="mt-4">
      <div className="flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500 mb-2.5">
        <span>{t("Analyzers")}</span>
        <span className="ticker">{done}/{steps.length}</span>
      </div>
      <ul className="space-y-2">
        {steps.map((step, i) => (
          <motion.li
            key={step.name}
            initial={{ opacity: 0, x: -6, filter: "blur(4px)" }}
            animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
            transition={{ delay: i * 0.05, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="flex items-center gap-3"
          >
            <Marker state={step.state} />
            <span
              className={clsx(
                "flex-1 min-w-0 truncate font-mono text-[11px] transition-colors duration-500",
                step.state === "running" && "shimmer-text text-signal-amber",
                step.state === "done" && "text-ink-200",
                step.state === "pending" && "text-ink-500",
                step.state === "skipped" && "text-ink-600 line-through",
              )}
            >
              {ANALYZER_LABELS[step.name] ? t(ANALYZER_LABELS[step.name]) : step.name}
            </span>
            {step.state === "done" && step.result?.execution_time != null && (
              <span className="font-mono text-[10px] text-ink-600 ticker">{step.result.execution_time.toFixed(1)}s</span>
            )}
          </motion.li>
        ))}
      </ul>
    </div>
  );
}
