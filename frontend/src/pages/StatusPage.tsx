import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Activity, Database, Zap, Cpu, Brain, HardDrive, RefreshCw, Mail } from "lucide-react";
import client from "../api/client";

interface ServiceProbe {
  status: "ok" | "down" | "skip";
  latency_ms?: number;
  error?: string;
  workers?: number;
  worker_names?: string[];
  active_tasks?: number;
  scheduled_tasks?: number;
  available_models?: string[];
  loaded_models?: string[];
  version?: string;
  endpoint?: string;
  reason?: string;
  backend?: string;
  from_email?: string;
  recent_failures?: number;
}

interface RetrainInfo {
  started_at: string;
  finished_at: string | null;
  status: string;
  samples_used: number;
  hf_revision: string | null;
  media_type: string;
}

interface SystemStatus {
  overall: "operational" | "degraded";
  checked_at: number;
  services: Record<string, ServiceProbe>;
  last_retrain: RetrainInfo | null;
}

const SERVICE_META: Record<string, { label: string; desc: string; Icon: typeof Activity }> = {
  api: { label: "API", desc: "Django REST gateway.", Icon: Activity },
  database: { label: "Database", desc: "PostgreSQL.", Icon: Database },
  redis: { label: "Redis", desc: "Celery broker + cache.", Icon: Zap },
  celery: { label: "Workers", desc: "Background analyzer pool.", Icon: Cpu },
  ollama: { label: "Vision LLM", desc: "Local inference - vision + text.", Icon: Brain },
  storage: { label: "Object Store", desc: "S3 blob store.", Icon: HardDrive },
  email: { label: "Email", desc: "Transactional mail (Resend).", Icon: Mail },
};

const ORDER = ["api", "database", "redis", "celery", "ollama", "storage", "email"];

function StatusDot({ status }: { status: ServiceProbe["status"] }) {
  const tone =
    status === "ok" ? "bg-signal-sage" :
    status === "skip" ? "bg-ink-500" :
    "bg-signal-blood";
  return (
    <span className="relative inline-flex">
      <span className={`w-2 h-2 rounded-full ${tone}`} />
      {status === "ok" && (
        <motion.span
          className={`absolute inset-0 rounded-full ${tone}`}
          animate={{ scale: [1, 2.4], opacity: [0.7, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
        />
      )}
    </span>
  );
}

export default function StatusPage() {
  const { data, isLoading, dataUpdatedAt } = useQuery<SystemStatus>({
    queryKey: ["system-status"],
    queryFn: () => client.get("/system/status/").then((r) => r.data),
    refetchInterval: 5000,
    staleTime: 0,
  });

  const services = data?.services || {};
  const overall = data?.overall;
  const lastRetrain = data?.last_retrain;

  return (
    <div className="max-w-3xl">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="label-mono flex items-center gap-2 mb-3">
          <span className="w-1.5 h-1.5 bg-signal-cyan rounded-full pulse-dot" />
          System / Status
        </div>
        <h1 className="font-display text-5xl lg:text-6xl text-ink-50 leading-none">
          {overall === "operational" ? (
            <>
              All systems <span className="italic text-signal-sage">operational</span>.
            </>
          ) : overall === "degraded" ? (
            <>
              Service <span className="italic text-signal-amber">degraded</span>.
            </>
          ) : (
            <>
              Probing<span className="italic text-iris">…</span>
            </>
          )}
        </h1>
        <p className="text-ink-300 mt-3 max-w-xl leading-relaxed">
          Real-time component health. Probed every 5s.
        </p>
      </motion.div>

      <div className="mt-10 case-card">
        <div className="flex items-center justify-between px-6 py-3 border-b border-white/5">
          <span className="label-mono">Probes</span>
          <span className="font-mono text-[10px] text-ink-500 ticker">
            {dataUpdatedAt ? `LAST: ${new Date(dataUpdatedAt).toLocaleTimeString()}` : "-"}
          </span>
        </div>

        <div className="divide-y divide-white/5">
          {ORDER.map((key, idx) => {
            const meta = SERVICE_META[key];
            const probe = services[key];
            const Icon = meta.Icon;
            return (
              <motion.div
                key={key}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: idx * 0.06 }}
                className="grid grid-cols-12 gap-4 px-6 py-5 items-center"
              >
                <div className="col-span-1 text-signal-amber/70">
                  <Icon size={18} strokeWidth={1.5} />
                </div>
                <div className="col-span-4">
                  <div className="font-display text-xl text-ink-50 leading-tight">{meta.label}</div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 mt-1">
                    {key.toUpperCase()}
                  </div>
                </div>
                <div className="col-span-5 text-sm text-ink-300 leading-relaxed">
                  {!probe || isLoading ? (
                    <span className="font-mono text-ink-500">probing…</span>
                  ) : probe.status === "ok" ? (
                    <span className="font-mono text-[11px] text-ink-300">
                      {probe.latency_ms != null && `${probe.latency_ms} ms`}
                      {probe.workers != null && ` · ${probe.workers} worker(s) · ${probe.active_tasks} active`}
                      {probe.loaded_models && probe.loaded_models.length > 0 && ` · loaded: ${probe.loaded_models.join(", ")}`}
                      {probe.available_models && probe.loaded_models?.length === 0 && ` · idle (${probe.available_models.length} models cached)`}
                      {probe.version && ` · v${probe.version}`}
                      {probe.backend && ` · via ${probe.backend}`}
                      {probe.recent_failures != null && probe.recent_failures > 0 && ` · ${probe.recent_failures} recent issue(s)`}
                    </span>
                  ) : probe.status === "skip" ? (
                    <span className="font-mono text-[11px] text-ink-500">{probe.reason || "skipped"}</span>
                  ) : (
                    <span className="font-mono text-[11px] text-signal-blood">{probe.error || "unreachable"}</span>
                  )}
                  <div className="text-xs text-ink-500 mt-1">{meta.desc}</div>
                </div>
                <div className="col-span-2 flex items-center justify-end gap-2">
                  <StatusDot status={probe?.status || "skip"} />
                  <span className={`font-mono text-[10px] uppercase tracking-[0.16em] ${
                    probe?.status === "ok" ? "text-signal-sage" :
                    probe?.status === "down" ? "text-signal-blood" :
                    "text-ink-500"
                  }`}>
                    {probe?.status || "-"}
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      <motion.div
        className="mt-6 case-card"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.5 }}
      >
        <div className="flex items-center gap-3 px-6 py-3 border-b border-white/5">
          <RefreshCw size={14} strokeWidth={1.5} className="text-signal-amber/70" />
          <span className="label-mono">Model Updates</span>
        </div>
        <div className="px-6 py-5">
          {lastRetrain ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-ink-500 mb-1">Last Retrain</div>
                <div className="font-mono text-xs text-ink-100">
                  {new Date(lastRetrain.started_at).toLocaleDateString()}
                </div>
              </div>
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-ink-500 mb-1">Samples</div>
                <div className="font-mono text-xs text-ink-100">{lastRetrain.samples_used}</div>
              </div>
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-ink-500 mb-1">Type</div>
                <div className="font-mono text-xs text-ink-100">{lastRetrain.media_type}</div>
              </div>
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-ink-500 mb-1">HF Revision</div>
                <div className="font-mono text-xs text-ink-100 truncate" title={lastRetrain.hf_revision || ""}>
                  {lastRetrain.hf_revision ? lastRetrain.hf_revision.slice(0, 10) : "n/a"}
                </div>
              </div>
            </div>
          ) : (
            <span className="font-mono text-[11px] text-ink-500">No successful retrains yet.</span>
          )}
        </div>
      </motion.div>

      <div className="mt-6 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 flex items-center gap-3">
        <span>Auto-refresh · 5s</span>
        <span className="text-ink-700">·</span>
        <span>Public endpoint</span>
        <span className="text-ink-700">·</span>
        <a href="https://api.prooflayer.cloud/api/v1/system/status/" className="hover:text-signal-amber transition-colors">
          GET /api/v1/system/status/
        </a>
      </div>
    </div>
  );
}
