import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { ExternalLink, Activity, Database, Zap, Cpu, Brain, HardDrive } from "lucide-react";
import { useAuthStore } from "../stores/authStore";
import client from "../api/client";

interface Credit {
  name: string;
  href: string;
  note: string;
  icon?: string;
  license?: string;
}

const FRONTEND: Credit[] = [
  { name: "React 18", href: "https://react.dev", note: "UI component framework", icon: "react" },
  { name: "React Router v7", href: "https://reactrouter.com", note: "Client-side routing", icon: "reactrouter" },
  { name: "Vite", href: "https://vitejs.dev", note: "Build tool + dev server", icon: "vite" },
  { name: "Tailwind CSS v3", href: "https://tailwindcss.com", note: "Utility-first CSS", icon: "tailwindcss" },
  { name: "Framer Motion", href: "https://www.framer.com/motion/", note: "Animation library" },
  { name: "Zustand", href: "https://github.com/pmndrs/zustand", note: "Client state management" },
  { name: "TanStack Query", href: "https://tanstack.com/query", note: "Server state + caching" },
  { name: "Lucide React", href: "https://lucide.dev", note: "Icon set" },
  { name: "Recharts", href: "https://recharts.org", note: "Chart components" },
  { name: "Axios", href: "https://axios-http.com", note: "HTTP client" },
];

const BACKEND: Credit[] = [
  { name: "Django 5", href: "https://djangoproject.com", note: "Web framework", icon: "django" },
  { name: "Django REST Framework", href: "https://www.django-rest-framework.org", note: "REST API toolkit" },
  { name: "SimpleJWT", href: "https://django-rest-framework-simplejwt.readthedocs.io", note: "JWT auth" },
  { name: "Celery", href: "https://docs.celeryq.dev", note: "Distributed task queue", icon: "celery" },
  { name: "Redis", href: "https://redis.io", note: "Broker + cache", icon: "redis" },
  { name: "PostgreSQL + pgvector", href: "https://github.com/pgvector/pgvector", note: "DB with vector search", icon: "postgresql" },
  { name: "MinIO", href: "https://min.io", note: "S3-compatible object store", icon: "minio" },
  { name: "Gunicorn", href: "https://gunicorn.org", note: "WSGI server" },
  { name: "boto3", href: "https://boto3.amazonaws.com/v1/documentation/api/latest/index.html", note: "S3 client" },
  { name: "spaCy", href: "https://spacy.io", note: "NLP - NER for fact-check", icon: "spacy" },
];

const ML: Credit[] = [
  {
    name: "CommunityForensics ViT-S/16",
    href: "https://huggingface.co/buildborderless/CommunityForensics-DeepfakeDet-ViT",
    note: "Primary deepfake detector. NeurIPS 2024.",
    icon: "huggingface",
    license: "Apache-2.0",
  },
  {
    name: "ViT Deepfake Detection (NPR)",
    href: "https://huggingface.co/Wvolf/ViT_Deepfake_Detection",
    note: "GAN-trained corroborator.",
    icon: "huggingface",
  },
  {
    name: "Deep-Fake-Detector-v2",
    href: "https://huggingface.co/prithivMLmods/Deep-Fake-Detector-v2-Model",
    note: "ViT binary classifier.",
    icon: "huggingface",
  },
  {
    name: "CLIP ViT-B/32",
    href: "https://huggingface.co/openai/clip-vit-base-patch32",
    note: "Semantic provenance embeddings (pgvector HNSW).",
    icon: "huggingface",
    license: "MIT",
  },
  {
    name: "LLaVA 7B",
    href: "https://huggingface.co/llava-hf/llava-1.5-7b-hf",
    note: "Vision LLM for image analysis via Ollama.",
    icon: "ollama",
    license: "Apache-2.0",
  },
  {
    name: "Qwen2.5-VL 3B",
    href: "https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct",
    note: "Vision-language model via Ollama.",
    icon: "ollama",
    license: "Apache-2.0",
  },
  {
    name: "Qwen2.5 3B",
    href: "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct",
    note: "Text AI detector via Ollama.",
    icon: "ollama",
    license: "Apache-2.0",
  },
  {
    name: "en_core_web_sm",
    href: "https://spacy.io/models/en",
    note: "spaCy English NER for fact-check.",
    license: "MIT",
  },
];

const INFRA: Credit[] = [
  { name: "Docker", href: "https://www.docker.com", note: "Container runtime", icon: "docker" },
  { name: "Caddy", href: "https://caddyserver.com", note: "Reverse proxy + auto-TLS", icon: "caddy" },
  { name: "Cloudflare Tunnel", href: "https://www.cloudflare.com/products/tunnel/", note: "Zero-trust ingress", icon: "cloudflare" },
  { name: "Tailscale", href: "https://tailscale.com", note: "WireGuard mesh VPN", icon: "tailscale" },
  { name: "Ubuntu", href: "https://ubuntu.com", note: "Server OS", icon: "ubuntu" },
  { name: "Sentry", href: "https://sentry.io", note: "Error tracking", icon: "sentry" },
];

const APIS: Credit[] = [
  { name: "Google Fact Check Tools", href: "https://developers.google.com/fact-check/tools/api", note: "Structured fact-check claims API", icon: "google" },
  { name: "DuckDuckGo Search", href: "https://duckduckgo.com", note: "Web search context for claims", icon: "duckduckgo" },
  { name: "Ollama", href: "https://ollama.com", note: "Local LLM inference server", icon: "ollama" },
  { name: "HuggingFace Hub", href: "https://huggingface.co", note: "Model hosting + datasets", icon: "huggingface" },
];

const SECTIONS: { label: string; items: Credit[] }[] = [
  { label: "Frontend", items: FRONTEND },
  { label: "Backend", items: BACKEND },
  { label: "ML Models", items: ML },
  { label: "Infrastructure", items: INFRA },
  { label: "External APIs & Datasets", items: APIS },
];

function CreditCard({ item, delay }: { item: Credit; delay: number }) {
  return (
    <motion.a
      href={item.href}
      target="_blank"
      rel="noopener noreferrer"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay }}
      className="case-card px-5 py-4 flex flex-col gap-2 hover:border-signal-amber/30 transition-colors group"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          {item.icon && (
            <img
              src={`https://cdn.simpleicons.org/${item.icon}`}
              alt=""
              className="w-4 h-4 opacity-70 group-hover:opacity-100 transition-opacity"
              loading="lazy"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          )}
          <span className="font-display text-base text-ink-50 leading-tight">{item.name}</span>
        </div>
        <ExternalLink size={12} strokeWidth={1.5} className="text-ink-600 group-hover:text-signal-amber transition-colors mt-0.5 shrink-0" />
      </div>
      <p className="font-mono text-[10px] text-ink-400 leading-relaxed">{item.note}</p>
      {item.license && (
        <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-600">{item.license}</span>
      )}
    </motion.a>
  );
}

interface ServiceProbe {
  status: "ok" | "down" | "skip";
  latency_ms?: number;
  error?: string;
  workers?: number;
  active_tasks?: number;
  loaded_models?: string[];
  available_models?: string[];
  reason?: string;
}

interface SystemStatus {
  overall: string;
  checked_at: number;
  services: Record<string, ServiceProbe>;
  last_retrain: {
    started_at: string;
    status: string;
    samples_used: number;
    media_type: string;
    hf_revision: string | null;
  } | null;
}

const SERVICE_META: Record<string, { label: string; Icon: typeof Activity }> = {
  api: { label: "API", Icon: Activity },
  database: { label: "Database", Icon: Database },
  redis: { label: "Redis", Icon: Zap },
  celery: { label: "Workers", Icon: Cpu },
  ollama: { label: "Vision LLM", Icon: Brain },
  storage: { label: "Object Store", Icon: HardDrive },
};

function AdminPanel() {
  const { data, isLoading } = useQuery<SystemStatus>({
    queryKey: ["system-status-credits"],
    queryFn: () => client.get("/system/status/").then((r) => r.data),
    refetchInterval: 10000,
    staleTime: 0,
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
      className="mt-12"
    >
      <div className="label-mono mb-4 flex items-center gap-2">
        <span className="w-1.5 h-1.5 bg-signal-violet rounded-full pulse-dot" />
        Admin / Live System
      </div>

      <div className="case-card">
        <div className="flex items-center justify-between px-6 py-3 border-b border-white/5">
          <span className="label-mono">Service Probes</span>
          <span className="font-mono text-[10px] text-ink-500">
            {data ? `overall: ${data.overall}` : "loading..."}
          </span>
        </div>
        <div className="divide-y divide-white/5">
          {Object.entries(SERVICE_META).map(([key, meta]) => {
            const probe = data?.services[key];
            const Icon = meta.Icon;
            return (
              <div key={key} className="grid grid-cols-12 gap-3 px-6 py-4 items-center">
                <div className="col-span-1 text-signal-amber/60">
                  <Icon size={16} strokeWidth={1.5} />
                </div>
                <div className="col-span-3">
                  <div className="font-display text-base text-ink-100">{meta.label}</div>
                  <div className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-600 mt-0.5">{key}</div>
                </div>
                <div className="col-span-6 font-mono text-[10px] text-ink-400">
                  {isLoading || !probe ? (
                    <span className="text-ink-600">probing...</span>
                  ) : probe.status === "ok" ? (
                    <span>
                      {probe.latency_ms != null && `${probe.latency_ms} ms`}
                      {probe.workers != null && ` · ${probe.workers}w · ${probe.active_tasks} active`}
                      {probe.loaded_models && probe.loaded_models.length > 0 && ` · ${probe.loaded_models.join(", ")}`}
                      {probe.available_models && probe.loaded_models?.length === 0 && ` · idle`}
                    </span>
                  ) : probe.status === "skip" ? (
                    <span className="text-ink-600">{probe.reason || "skipped"}</span>
                  ) : (
                    <span className="text-signal-blood">{probe.error || "unreachable"}</span>
                  )}
                </div>
                <div className="col-span-2 flex justify-end">
                  <span className={`font-mono text-[9px] uppercase tracking-[0.16em] px-2 py-0.5 rounded-sm ${
                    probe?.status === "ok"
                      ? "text-signal-sage bg-signal-sage/10"
                      : probe?.status === "down"
                      ? "text-signal-blood bg-signal-blood/10"
                      : "text-ink-500 bg-white/5"
                  }`}>
                    {probe?.status ?? "-"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {data?.last_retrain && (
        <div className="mt-4 case-card px-6 py-5">
          <div className="label-mono mb-3">Last Retrain</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500 mb-1">Date</div>
              <div className="font-mono text-xs text-ink-100">
                {new Date(data.last_retrain.started_at).toLocaleDateString()}
              </div>
            </div>
            <div>
              <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500 mb-1">Type</div>
              <div className="font-mono text-xs text-ink-100">{data.last_retrain.media_type}</div>
            </div>
            <div>
              <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500 mb-1">Samples</div>
              <div className="font-mono text-xs text-ink-100">{data.last_retrain.samples_used}</div>
            </div>
            <div>
              <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500 mb-1">Status</div>
              <div className="font-mono text-xs text-ink-100">{data.last_retrain.status}</div>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
}

export default function CreditsPage() {
  const { user } = useAuthStore();

  return (
    <div className="max-w-5xl">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="label-mono flex items-center gap-2 mb-3">
          <span className="w-1.5 h-1.5 bg-signal-cyan rounded-full" />
          Credits
        </div>
        <h1 className="font-display text-5xl lg:text-6xl text-ink-50 leading-none">
          Open-source <span className="italic text-iris">authors</span>.
        </h1>
        <p className="text-ink-300 mt-3 max-w-xl leading-relaxed">
          ProofLayer is built on the work of these projects and researchers. All models, libraries, and tools are credited here.
        </p>
      </motion.div>

      <div className="mt-12 space-y-10">
        {SECTIONS.map((section, sIdx) => (
          <div key={section.label}>
            <div className="label-mono mb-4">{section.label}</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {section.items.map((item, iIdx) => (
                <CreditCard key={item.name} item={item} delay={sIdx * 0.05 + iIdx * 0.03} />
              ))}
            </div>
          </div>
        ))}
      </div>

      {user?.is_staff && <AdminPanel />}

      <div className="mt-10 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-600">
        ProofLayer is open-source. Contributions welcome.
      </div>
    </div>
  );
}
