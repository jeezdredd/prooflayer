import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import client from "../api/client";
import { msg, t } from "../i18n";

type ProbeState = "ok" | "down" | "skip";

interface MiniStatus {
  overall: "operational" | "degraded";
  services: Record<string, { status: ProbeState; ensemble?: string }>;
  verdict_timing?: { image_median_s: number | null };
}

const ORDER = ["api", "database", "redis", "celery", "analyzers", "ollama", "storage", "email"];
const HEIGHTS = [5, 12, 7, 10];

const GROUPS: { label: string; note: string; keys: string[] }[] = [
  { label: msg("Checking work"), note: msg("Detectors, workers and language models"), keys: ["celery", "analyzers", "ollama"] },
  { label: msg("Files and reports"), note: msg("Uploads, PDF reports, class records"), keys: ["storage", "database"] },
  { label: msg("Sign-in and email"), note: msg("Accounts, invitations, notifications"), keys: ["api", "redis", "email"] },
];

const TONE: Record<ProbeState | "unknown", string> = {
  ok: "bg-signal-sage",
  skip: "bg-ink-500",
  down: "bg-signal-blood",
  unknown: "bg-ink-600",
};

function groupState(status: MiniStatus | undefined, keys: string[]): ProbeState | "unknown" {
  if (!status) return "unknown";
  const states = keys.map((k) => status.services[k]?.status ?? "skip");
  if (states.includes("down")) return "down";
  return states.includes("ok") ? "ok" : "skip";
}

export default function StatusPulse() {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const { data, isError } = useQuery<MiniStatus>({
    queryKey: ["system-status-mini"],
    queryFn: () => client.get("/system/status/").then((r) => r.data),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const healthy = data?.overall === "operational";
  const headline = !data ? (isError ? t("Status unknown") : t("Checking status…")) : healthy ? t("All systems working") : t("Checks may be slower");
  const median = data?.verdict_timing?.image_median_s;
  const tribunal = data?.services.analyzers?.ensemble;

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={headline}
        className="group flex items-center gap-2 border border-[var(--line-strong)] px-2.5 h-7 hover:border-ink-500 transition-colors"
      >
        <span className="relative flex w-1.5 h-1.5">
          {healthy && <span className="absolute inset-0 rounded-full bg-signal-sage opacity-60 animate-ping" />}
          <span className={clsx("relative w-1.5 h-1.5 rounded-full", data ? (healthy ? TONE.ok : TONE.down) : TONE.unknown)} />
        </span>
        <span className="flex items-end gap-[2px] h-3" aria-hidden>
          {ORDER.map((key, i) => (
            <motion.span
              key={key}
              className={clsx("w-[2px] rounded-full", TONE[data?.services[key]?.status ?? "unknown"])}
              initial={{ height: 3 }}
              animate={{ height: data ? HEIGHTS[i % HEIGHTS.length] : 3 }}
              transition={{ delay: i * 0.04, type: "spring", stiffness: 260, damping: 18 }}
            />
          ))}
        </span>
        <span className="hidden md:inline text-ink-300 group-hover:text-ink-100">{headline}</span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-9 z-30 w-72 max-w-[calc(100vw-2.5rem)] border border-[var(--line-strong)] bg-ink-950 shadow-xl p-4"
          >
            <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-3">{headline}</div>
            <ul className="space-y-3">
              {GROUPS.map((g) => {
                const state = groupState(data, g.keys);
                return (
                  <li key={g.label} className="flex items-start gap-3">
                    <span className={clsx("mt-1.5 w-1.5 h-1.5 rounded-full shrink-0", TONE[state])} />
                    <div className="min-w-0 font-sans">
                      <div className="text-sm text-ink-100">
                        {t(g.label)}
                        {state === "down" && <span className="text-signal-blood"> · {t("interrupted")}</span>}
                      </div>
                      <div className="text-xs text-ink-500">{t(g.note)}</div>
                    </div>
                  </li>
                );
              })}
            </ul>
            {(median || tribunal) && (
              <div className="mt-4 pt-3 border-t border-[var(--line-strong)] font-mono text-[11px] text-ink-400 space-y-1">
                {median ? <div>{t("A check takes about {n} s right now", { n: Math.round(median) })}</div> : null}
                {tribunal ? <div>{t("Verdicts by {name}", { name: tribunal })}</div> : null}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
