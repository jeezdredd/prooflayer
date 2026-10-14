import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Activity, Brain, Cpu, Database, GraduationCap, HardDrive, Layers, Mail, Zap } from "lucide-react";
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

interface RunInfo {
  status: string;
  started_at: string;
  finished_at: string | null;
  samples_used: number;
  error: string;
}

interface TrainingQueue {
  media_type: string;
  new_samples: number;
  needed: number;
  last_success: RunInfo | null;
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

const STATE: Record<ServiceProbe["status"], { word: string; chip: string; dot: string }> = {
  ok: { word: msg("Working"), chip: "text-signal-sage bg-signal-sage/10 border-signal-sage/30", dot: "bg-signal-sage" },
  down: { word: msg("Down"), chip: "text-signal-blood bg-signal-blood/10 border-signal-blood/40", dot: "bg-signal-blood" },
  skip: { word: msg("Not checked"), chip: "text-ink-400 bg-ink-800 border-[var(--line-strong)]", dot: "bg-ink-500" },
};

const SKIP_REASON = /^only (\d+) new approved samples, need (\d+)$/;

function facts(key: string, probe: ServiceProbe): string[] {
  const out: string[] = [];
  if (probe.latency_ms != null) out.push(t("{n} ms", { n: probe.latency_ms }));
  if (key === "celery" && probe.workers != null) {
    out.push(t("workers: {n}", { n: probe.workers }));
    out.push(t("busy: {n}", { n: probe.active_tasks ?? 0 }));
  }
  if (key === "ollama") {
    if (probe.loaded_models?.length) out.push(t("loaded: {names}", { names: probe.loaded_models.join(", ") }));
    else if (probe.available_models) out.push(t("idle, {n} models ready", { n: probe.available_models.length }));
  }
  if (key === "analyzers" && probe.active != null && probe.expected != null) {
    out.push(t("{active} of {expected} active", { active: probe.active, expected: probe.expected }));
    if (probe.ensemble) out.push(probe.ensemble);
  }
  if (key === "redis" && probe.version) out.push(`v${probe.version}`);
  if (key === "email" && probe.backend) out.push(t("via {name}", { name: probe.backend }));
  if (probe.recent_failures) out.push(t("recent issues: {n}", { n: probe.recent_failures }));
  return out;
}

function formatDate(value: string | null | undefined, withTime = false): string {
  if (!value) return "-";
  const date = new Date(value);
  return withTime
    ? date.toLocaleString(locale(), { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString(locale(), { day: "numeric", month: "long", year: "numeric" });
}

function attemptText(run: RunInfo): string {
  if (run.status === "success") return t("Retrained on {n} new examples", { n: run.samples_used });
  if (run.status === "skipped") {
    const m = SKIP_REASON.exec(run.error);
    return m ? t("Skipped: {have} new examples, {need} needed", { have: m[1], need: m[2] }) : t("Skipped");
  }
  if (run.status === "failed") return t("Failed: {reason}", { reason: run.error || "-" });
  return t("In progress");
}

function ServiceCard({ item, probe, index }: { item: (typeof SERVICES)[number]; probe?: ServiceProbe; index: number }) {
  const Icon = item.Icon;
  const state = STATE[probe?.status ?? "skip"];
  const details = probe ? facts(item.key, probe) : [];
  const problem = probe?.status === "down" ? probe.error : probe?.status === "skip" ? probe.reason : undefined;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.03 }}
      className="case-card p-4 flex gap-3.5"
    >
      <div className="w-9 h-9 shrink-0 rounded-md border border-[var(--line-strong)] flex items-center justify-center text-ink-300">
        <Icon size={16} strokeWidth={1.5} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="text-[15px] text-ink-50 leading-tight">{t(item.label)}</div>
          <span className={clsx("shrink-0 inline-flex items-center gap-1.5 border px-2 py-0.5 text-[11px] rounded-full", state.chip)}>
            <span className={clsx("w-1.5 h-1.5 rounded-full", state.dot)} />
            {probe ? t(state.word) : t("checking…")}
          </span>
        </div>
        <div className="text-xs text-ink-400 mt-1 leading-snug">{t(item.role)}</div>
        {problem && <div className="text-xs text-signal-blood/90 mt-1.5 break-words">{t(problem)}</div>}
        {details.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2.5">
            {details.map((d) => (
              <span key={d} className="font-mono text-[10px] text-ink-300 bg-white/[0.03] border border-[var(--line)] px-1.5 py-0.5 rounded">{d}</span>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}

function TrainingCard({ training }: { training: TrainingQueue }) {
  const pct = Math.min(100, Math.round((training.new_samples / Math.max(training.needed, 1)) * 100));
  return (
    <div className="case-card p-5">
      <div className="flex items-start gap-3.5">
        <div className="w-9 h-9 shrink-0 rounded-md border border-[var(--line-strong)] flex items-center justify-center text-ink-300">
          <GraduationCap size={16} strokeWidth={1.5} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[15px] text-ink-50">{t("Detector retraining")}</div>
          <p className="text-xs text-ink-400 mt-1 leading-relaxed max-w-xl">
            {t("Our image detector retrains itself every week once reviewers have labelled enough new uploads as real or AI. Until then it keeps the current model.")}
          </p>
        </div>
      </div>

      <div className="mt-5">
        <div className="flex items-baseline justify-between text-xs mb-1.5">
          <span className="text-ink-300">{t("New labelled examples")}</span>
          <span className="font-mono text-ink-100 tabular-nums">{training.new_samples} / {training.needed}</span>
        </div>
        <div className="h-1.5 bg-ink-800 rounded-full overflow-hidden">
          <div className="h-full bg-signal-amber rounded-full transition-all duration-700" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <dl className="grid sm:grid-cols-3 gap-4 mt-5 text-xs">
        <div>
          <dt className="text-ink-500">{t("Last retrained")}</dt>
          <dd className="text-ink-100 mt-1">{formatDate(training.last_success?.finished_at)}</dd>
          {training.last_success && <dd className="text-ink-500 mt-0.5">{t("on {n} examples", { n: training.last_success.samples_used })}</dd>}
        </div>
        <div>
          <dt className="text-ink-500">{t("Last attempt")}</dt>
          <dd className="text-ink-100 mt-1">{formatDate(training.last_attempt?.started_at, true)}</dd>
          {training.last_attempt && <dd className="text-ink-500 mt-0.5">{attemptText(training.last_attempt)}</dd>}
        </div>
        <div>
          <dt className="text-ink-500">{t("Next check")}</dt>
          <dd className="text-ink-100 mt-1">{formatDate(training.next_run, true)}</dd>
          <dd className="text-ink-500 mt-0.5">{t("every Sunday")}</dd>
        </div>
      </dl>
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
  const down = SERVICES.filter((s) => services[s.key]?.status === "down");
  const tone = overall === "operational" ? "border-signal-sage/40 bg-signal-sage/[0.06]" : overall === "degraded" ? "border-signal-amber/50 bg-signal-amber/[0.06]" : "border-[var(--line-strong)]";
  const dot = overall === "operational" ? "bg-signal-sage" : overall === "degraded" ? "bg-signal-amber" : "bg-ink-500";

  return (
    <div className="max-w-4xl">
      <div className="label-mono mb-3">{t("System status")}</div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className={clsx("border rounded-lg p-5 flex items-center gap-4", tone)}
      >
        <span className="relative inline-flex shrink-0">
          <span className={clsx("w-3 h-3 rounded-full", dot)} />
          {overall === "operational" && (
            <motion.span
              className={clsx("absolute inset-0 rounded-full", dot)}
              animate={{ scale: [1, 2.4], opacity: [0.6, 0] }}
              transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
            />
          )}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-xl text-ink-50">
            {overall === "operational"
              ? t("All systems are working")
              : overall === "degraded"
              ? t("Some services have problems")
              : t("Checking services…")}
          </div>
          <div className="text-xs text-ink-400 mt-1">
            {down.length > 0
              ? t("Affected: {names}", { names: down.map((s) => t(s.label)).join(", ") })
              : t("Checked every 5 seconds")}
            {dataUpdatedAt ? ` · ${t("last check {time}", { time: new Date(dataUpdatedAt).toLocaleTimeString(locale()) })}` : ""}
          </div>
        </div>
      </motion.div>

      <div className="grid sm:grid-cols-2 gap-3 mt-6">
        {SERVICES.map((item, i) => (
          <ServiceCard key={item.key} item={item} probe={services[item.key]} index={i} />
        ))}
      </div>

      {data?.training && (
        <div className="mt-8">
          <div className="label-mono mb-3">{t("Models")}</div>
          <TrainingCard training={data.training} />
        </div>
      )}

      <div className="mt-8 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-600">
        {t("Public endpoint")} ·{" "}
        <a href="https://api.prooflayer.cloud/api/v1/system/status/" className="hover:text-signal-amber transition-colors">
          GET /api/v1/system/status/
        </a>
      </div>
    </div>
  );
}
