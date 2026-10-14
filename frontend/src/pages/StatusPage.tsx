import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Activity, Brain, Cpu, Database, HardDrive, Layers, Mail, Zap } from "lucide-react";
import client from "../api/client";
import { locale, msg, t } from "../i18n";

interface ServiceProbe {
  status: "ok" | "down" | "skip";
  latency_ms?: number;
  error?: string;
  workers?: number;
  active_tasks?: number;
  available_models?: string[];
  loaded_models?: string[];
  version?: string;
  reason?: string;
  backend?: string;
  recent_failures?: number;
  active?: number;
  expected?: number;
  ensemble?: string;
}

interface HoldoutNumbers {
  real: number;
  ai: number;
  real_fake: number;
  real_suspicious: number;
  ai_caught: number;
  ai_authentic: number;
}

interface RunInfo {
  status: string;
  started_at: string;
  finished_at: string | null;
  samples_used: number;
  error: string;
  metrics?: { live?: HoldoutNumbers; candidate?: HoldoutNumbers; fetched?: number; db_samples?: number };
}

interface TrainingQueue {
  new_samples: number;
  needed: number;
  last_success: RunInfo | null;
  live_model_trained_at?: string | null;
  last_attempt: RunInfo | null;
  next_run: string;
}

interface SystemStatus {
  overall: "operational" | "degraded";
  services: Record<string, ServiceProbe>;
  training?: TrainingQueue;
}

const SERVICES: { key: string; label: string; role: string; Icon: typeof Activity }[] = [
  { key: "api", label: msg("API"), role: msg("Accepts uploads and serves results"), Icon: Activity },
  { key: "database", label: msg("Database"), role: msg("Accounts, classes, verdicts"), Icon: Database },
  { key: "redis", label: msg("Queue"), role: msg("Hands checks to the workers"), Icon: Zap },
  { key: "celery", label: msg("Workers"), role: msg("Run the analyzers in the background"), Icon: Cpu },
  { key: "ollama", label: msg("Language models"), role: msg("Vision model, fact-check and assignment shadow"), Icon: Brain },
  { key: "storage", label: msg("File storage"), role: msg("Uploaded files and reports"), Icon: HardDrive },
  { key: "email", label: msg("Email"), role: msg("Sign-in and billing letters"), Icon: Mail },
  { key: "analyzers", label: msg("Tribunal"), role: msg("Every detector is loaded and configured"), Icon: Layers },
];

const STATE: Record<ServiceProbe["status"], { word: string; text: string; dot: string }> = {
  ok: { word: msg("Working"), text: "text-signal-sage", dot: "bg-signal-sage" },
  down: { word: msg("Down"), text: "text-signal-blood", dot: "bg-signal-blood" },
  skip: { word: msg("Not checked"), text: "text-ink-400", dot: "bg-ink-500" },
};

const SKIP_REASON = /^only (\d+) new approved samples, need (\d+)$/;

function detail(key: string, probe: ServiceProbe): string {
  const parts: string[] = [];
  if (key === "celery" && probe.workers != null) parts.push(t("workers: {n}", { n: probe.workers }), t("busy: {n}", { n: probe.active_tasks ?? 0 }));
  if (key === "ollama") {
    if (probe.loaded_models?.length) parts.push(t("loaded: {names}", { names: probe.loaded_models.join(", ") }));
    else if (probe.available_models) parts.push(t("idle, {n} models ready", { n: probe.available_models.length }));
  }
  if (key === "analyzers" && probe.active != null && probe.expected != null) parts.push(t("{active} of {expected} active", { active: probe.active, expected: probe.expected }));
  if (key === "redis" && probe.version) parts.push(`v${probe.version}`);
  if (key === "email" && probe.backend) parts.push(t("via {name}", { name: probe.backend }));
  if (probe.recent_failures) parts.push(t("recent issues: {n}", { n: probe.recent_failures }));
  if (probe.status === "down" && probe.error) parts.push(t(probe.error));
  if (probe.status === "skip" && probe.reason) parts.push(t(probe.reason));
  return parts.join(" · ");
}

function formatDate(value: string | null | undefined, withTime = false): string {
  if (!value) return "-";
  const date = new Date(value);
  return withTime
    ? date.toLocaleString(locale(), { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString(locale(), { day: "numeric", month: "long", year: "numeric" });
}

function attemptText(run: RunInfo): { text: string; tone: string } {
  if (run.status === "success") return { text: t("New model promoted"), tone: "text-signal-sage" };
  if (run.status === "rejected") return { text: t("Candidate rejected: {reason}", { reason: run.error }), tone: "text-signal-amber" };
  if (run.status === "skipped") {
    const m = SKIP_REASON.exec(run.error);
    return { text: m ? t("Skipped: {have} new examples, {need} needed", { have: m[1], need: m[2] }) : t("Skipped: {reason}", { reason: t(run.error) }), tone: "text-ink-400" };
  }
  if (run.status === "failed") return { text: t("Failed: {reason}", { reason: run.error || "-" }), tone: "text-signal-blood" };
  return { text: t("In progress"), tone: "text-signal-amber" };
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="bg-ink-950 px-4 py-3.5">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{label}</div>
      <div className={clsx("font-display text-2xl mt-1 tabular-nums", tone ?? "text-ink-50")}>{value}</div>
    </div>
  );
}

function HoldoutTable({ live, candidate }: { live: HoldoutNumbers; candidate: HoldoutNumbers }) {
  const rows: [string, keyof HoldoutNumbers, boolean][] = [
    [msg("AI caught"), "ai_caught", true],
    [msg("AI called authentic"), "ai_authentic", false],
    [msg("Real photos called AI"), "real_fake", false],
    [msg("Real photos called suspicious"), "real_suspicious", false],
  ];
  return (
    <table className="w-full text-xs mt-4">
      <thead>
        <tr className="text-ink-500 font-mono text-[10px] uppercase tracking-[0.14em]">
          <th className="text-left font-normal py-1.5">{t("Held-out check")}</th>
          <th className="text-right font-normal py-1.5">{t("Live model")}</th>
          <th className="text-right font-normal py-1.5">{t("Candidate")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, key, higherBetter]) => {
          const better = higherBetter ? candidate[key] > live[key] : candidate[key] < live[key];
          const worse = higherBetter ? candidate[key] < live[key] : candidate[key] > live[key];
          return (
            <tr key={key} className="border-t border-[var(--line)]">
              <td className="py-1.5 text-ink-300">{t(label)}</td>
              <td className="py-1.5 text-right tabular-nums text-ink-200">{live[key]}</td>
              <td className={clsx("py-1.5 text-right tabular-nums", better ? "text-signal-sage" : worse ? "text-signal-blood" : "text-ink-200")}>{candidate[key]}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function TrainingBlock({ training }: { training: TrainingQueue }) {
  const pct = Math.min(100, Math.round((training.new_samples / Math.max(training.needed, 1)) * 100));
  const attempt = training.last_attempt ? attemptText(training.last_attempt) : null;
  const metrics = training.last_attempt?.metrics;
  return (
    <div className="case-card p-5">
      <p className="text-sm text-ink-300 leading-relaxed max-w-2xl">
        {t("Every Sunday the image detector pulls fresh examples from OpenFake and reviewed uploads, trains a candidate and checks it on a frozen held-out set. The candidate replaces the live model only if no real photo is called AI and detection improves.")}
      </p>

      <div className="mt-5">
        <div className="flex items-baseline justify-between text-xs mb-1.5">
          <span className="text-ink-300">{t("New examples since the last model")}</span>
          <span className="font-mono text-ink-100 tabular-nums">{training.new_samples} / {training.needed}</span>
        </div>
        <div className="h-1.5 bg-ink-800 rounded-full overflow-hidden">
          <div className="h-full bg-signal-amber rounded-full transition-all duration-700" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <dl className="grid sm:grid-cols-3 gap-4 mt-5 text-xs">
        <div>
          <dt className="text-ink-500">{t("Model in use since")}</dt>
          <dd className="text-ink-100 mt-1">{formatDate(training.live_model_trained_at ?? training.last_success?.finished_at)}</dd>
        </div>
        <div>
          <dt className="text-ink-500">{t("Last attempt")}</dt>
          <dd className="text-ink-100 mt-1">{formatDate(training.last_attempt?.started_at, true)}</dd>
          {attempt && <dd className={clsx("mt-0.5", attempt.tone)}>{attempt.text}</dd>}
        </div>
        <div>
          <dt className="text-ink-500">{t("Next attempt")}</dt>
          <dd className="text-ink-100 mt-1">{formatDate(training.next_run, true)}</dd>
          <dd className="text-ink-500 mt-0.5">{t("every Sunday")}</dd>
        </div>
      </dl>

      {metrics?.live && metrics?.candidate && <HoldoutTable live={metrics.live} candidate={metrics.candidate} />}
    </div>
  );
}

export default function StatusPage() {
  const { data, dataUpdatedAt } = useQuery<SystemStatus>({
    queryKey: ["system-status"],
    queryFn: () => client.get("/system/status/").then((r) => r.data),
    refetchInterval: 5000,
    staleTime: 0,
  });

  const services = data?.services ?? {};
  const overall = data?.overall;
  const working = SERVICES.filter((s) => services[s.key]?.status === "ok").length;
  const roster = services.analyzers;

  return (
    <div className="max-w-5xl">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <div className="label-mono flex items-center gap-2 mb-3">
          <span className={clsx("w-1.5 h-1.5 rounded-full pulse-dot", overall === "degraded" ? "bg-signal-amber" : "bg-signal-sage")} />
          {t("System / Status")}
        </div>
        <h1 className="font-display text-5xl lg:text-6xl text-ink-50 leading-none">
          {overall === "operational" ? (
            <>{t("All systems")} <span className="italic text-signal-sage">{t("operational")}</span>.</>
          ) : overall === "degraded" ? (
            <>{t("Service")} <span className="italic text-signal-amber">{t("degraded")}</span>.</>
          ) : (
            <>{t("Probing")}<span className="italic text-iris">…</span></>
          )}
        </h1>
        <p className="text-ink-300 mt-3">
          {t("Real-time component health. Probed every 5s.")}
          {dataUpdatedAt ? ` ${t("Last check {time}.", { time: new Date(dataUpdatedAt).toLocaleTimeString(locale()) })}` : ""}
        </p>
      </motion.div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-[var(--line-strong)] border border-[var(--line-strong)] mt-8">
        <Stat label={t("Services working")} value={data ? `${working} / ${SERVICES.length}` : "-"} tone={data && working < SERVICES.length ? "text-signal-amber" : "text-signal-sage"} />
        <Stat label={t("Tribunal")} value={roster?.ensemble?.replace("Tribunal ", "") ?? "-"} />
        <Stat label={t("Active analyzers")} value={roster?.active != null ? `${roster.active} / ${roster.expected}` : "-"} />
        <Stat label={t("Database latency")} value={services.database?.latency_ms != null ? t("{n} ms", { n: services.database.latency_ms }) : "-"} />
      </div>

      <div className="label-mono mt-10 mb-3">{t("Services")}</div>
      <div className="case-card divide-y divide-[var(--line)]">
        {SERVICES.map((item) => {
          const probe = services[item.key];
          const state = STATE[probe?.status ?? "skip"];
          const Icon = item.Icon;
          return (
            <div key={item.key} className="flex items-center gap-4 px-5 py-3.5">
              <Icon size={16} strokeWidth={1.5} className="text-ink-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-3 flex-wrap">
                  <span className="text-sm text-ink-50">{t(item.label)}</span>
                  <span className="text-xs text-ink-500">{t(item.role)}</span>
                </div>
                {probe && detail(item.key, probe) && <div className="font-mono text-[11px] text-ink-400 mt-0.5 truncate">{detail(item.key, probe)}</div>}
              </div>
              {probe?.latency_ms != null && <span className="font-mono text-[11px] text-ink-500 tabular-nums hidden sm:inline">{t("{n} ms", { n: probe.latency_ms })}</span>}
              <span className={clsx("flex items-center gap-1.5 text-xs shrink-0 w-28 justify-end", state.text)}>
                <span className={clsx("w-1.5 h-1.5 rounded-full", state.dot)} />
                {probe ? t(state.word) : t("checking…")}
              </span>
            </div>
          );
        })}
      </div>

      {data?.training && (
        <>
          <div className="label-mono mt-10 mb-3">{t("Self-improving detector")}</div>
          <TrainingBlock training={data.training} />
        </>
      )}

      <div className="mt-8 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-600">
        {t("Public endpoint")} ·{" "}
        <a href="https://api.prooflayer.cloud/api/v1/system/status/" className="hover:text-signal-amber transition-colors">GET /api/v1/system/status/</a>
      </div>
    </div>
  );
}
