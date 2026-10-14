import { motion } from "motion/react";
import { ExternalLink } from "lucide-react";
import { msg, t } from "../i18n";

interface Credit {
  name: string;
  href: string;
  note: string;
  icon?: string;
  license?: string;
}

const FRONTEND: Credit[] = [
  { name: "React 18", href: "https://react.dev", note: msg("UI component framework"), icon: "react" },
  { name: "React Router v7", href: "https://reactrouter.com", note: msg("Client-side routing"), icon: "reactrouter" },
  { name: "Vite", href: "https://vitejs.dev", note: msg("Build tool + dev server"), icon: "vite" },
  { name: "Tailwind CSS v3", href: "https://tailwindcss.com", note: msg("Utility-first CSS"), icon: "tailwindcss" },
  { name: "Framer Motion", href: "https://www.framer.com/motion/", note: msg("Animation library") },
  { name: "Zustand", href: "https://github.com/pmndrs/zustand", note: msg("Client state management") },
  { name: "TanStack Query", href: "https://tanstack.com/query", note: msg("Server state + caching") },
  { name: "Lucide React", href: "https://lucide.dev", note: msg("Icon set") },
  { name: "Recharts", href: "https://recharts.org", note: msg("Chart components") },
  { name: "Axios", href: "https://axios-http.com", note: msg("HTTP client") },
];

const BACKEND: Credit[] = [
  { name: "Django 5", href: "https://djangoproject.com", note: msg("Web framework"), icon: "django" },
  { name: "Django REST Framework", href: "https://www.django-rest-framework.org", note: msg("REST API toolkit") },
  { name: "SimpleJWT", href: "https://django-rest-framework-simplejwt.readthedocs.io", note: msg("JWT auth") },
  { name: "Celery", href: "https://docs.celeryq.dev", note: msg("Distributed task queue"), icon: "celery" },
  { name: "Redis", href: "https://redis.io", note: msg("Broker + cache"), icon: "redis" },
  { name: "PostgreSQL + pgvector", href: "https://github.com/pgvector/pgvector", note: msg("DB with vector search"), icon: "postgresql" },
  { name: "MinIO", href: "https://min.io", note: msg("S3-compatible object store"), icon: "minio" },
  { name: "Gunicorn / Daphne", href: "https://gunicorn.org", note: msg("WSGI/ASGI server") },
  { name: "boto3", href: "https://boto3.amazonaws.com/v1/documentation/api/latest/index.html", note: msg("S3 client") },
  { name: "spaCy", href: "https://spacy.io", note: msg("NLP - NER for fact-check") },
  { name: "Django Channels", href: "https://channels.readthedocs.io", note: msg("WebSocket + ASGI") },
];

const ML: Credit[] = [
  {
    name: "CommunityForensics ViT-S/16",
    href: "https://huggingface.co/buildborderless/CommunityForensics-DeepfakeDet-ViT",
    note: msg("Primary deepfake detector. NeurIPS 2024."),
    icon: "huggingface",
    license: "Apache-2.0",
  },
  {
    name: "ViT Deepfake Detection (NPR)",
    href: "https://huggingface.co/Wvolf/ViT_Deepfake_Detection",
    note: msg("GAN-trained corroborator."),
    icon: "huggingface",
  },
  {
    name: "Deep-Fake-Detector-v2",
    href: "https://huggingface.co/prithivMLmods/Deep-Fake-Detector-v2-Model",
    note: msg("ViT binary classifier."),
    icon: "huggingface",
  },
  {
    name: "CLIP ViT-B/32",
    href: "https://huggingface.co/openai/clip-vit-base-patch32",
    note: msg("Semantic provenance embeddings (pgvector HNSW)."),
    icon: "huggingface",
    license: "MIT",
  },
  {
    name: "LLaVA 7B",
    href: "https://huggingface.co/llava-hf/llava-1.5-7b-hf",
    note: msg("Vision LLM for image analysis via Ollama."),
    icon: "ollama",
    license: "Apache-2.0",
  },
  {
    name: "Qwen2.5-VL 3B",
    href: "https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct",
    note: msg("Vision-language model via Ollama."),
    icon: "ollama",
    license: "Apache-2.0",
  },
  {
    name: "Qwen2.5 3B",
    href: "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct",
    note: msg("Text AI detector via Ollama."),
    icon: "ollama",
    license: "Apache-2.0",
  },
  {
    name: "en_core_web_sm",
    href: "https://spacy.io/models/en",
    note: msg("spaCy English NER for fact-check."),
    license: "MIT",
  },
];

const INFRA: Credit[] = [
  { name: "Docker", href: "https://www.docker.com", note: msg("Container runtime"), icon: "docker" },
  { name: "Caddy", href: "https://caddyserver.com", note: msg("Reverse proxy + auto-TLS"), icon: "caddy" },
  { name: "Cloudflare Tunnel", href: "https://www.cloudflare.com/products/tunnel/", note: msg("Zero-trust ingress"), icon: "cloudflare" },
  { name: "Tailscale", href: "https://tailscale.com", note: msg("WireGuard mesh VPN"), icon: "tailscale" },
  { name: "Ubuntu", href: "https://ubuntu.com", note: msg("Server OS"), icon: "ubuntu" },
  { name: "Sentry", href: "https://sentry.io", note: msg("Error tracking"), icon: "sentry" },
];

const APIS: Credit[] = [
  { name: "Google Fact Check Tools", href: "https://developers.google.com/fact-check/tools/api", note: msg("Structured fact-check claims API"), icon: "google" },
  { name: "DuckDuckGo Search", href: "https://duckduckgo.com", note: msg("Web search context for claims"), icon: "duckduckgo" },
  { name: "Ollama", href: "https://ollama.com", note: msg("Local LLM inference server"), icon: "ollama" },
  { name: "HuggingFace Hub", href: "https://huggingface.co", note: msg("Model hosting + datasets"), icon: "huggingface" },
];

const SECTIONS: { label: string; items: Credit[] }[] = [
  { label: msg("Frontend"), items: FRONTEND },
  { label: msg("Backend"), items: BACKEND },
  { label: msg("ML Models"), items: ML },
  { label: msg("Infrastructure"), items: INFRA },
  { label: msg("External APIs & Datasets"), items: APIS },
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
      <p className="font-mono text-[10px] text-ink-400 leading-relaxed">{t(item.note)}</p>
      {item.license && (
        <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-600">{item.license}</span>
      )}
    </motion.a>
  );
}

export default function CreditsPage() {
  return (
    <div className="max-w-5xl">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="label-mono flex items-center gap-2 mb-3">
          <span className="w-1.5 h-1.5 bg-signal-cyan rounded-full" />
          {t("Credits")}
        </div>
        <h1 className="font-display text-5xl lg:text-6xl text-ink-50 leading-none">
          {t("Open-source")} <span className="italic text-iris">{t("authors")}</span>.
        </h1>
        <p className="text-ink-300 mt-3 max-w-xl leading-relaxed">
          {t("ProofLayer is built on the work of these projects and researchers. All models, libraries, and tools are credited here.")}
        </p>
      </motion.div>

      <div className="mt-12 space-y-10">
        {SECTIONS.map((section, sIdx) => (
          <div key={section.label}>
            <div className="label-mono mb-4">{t(section.label)}</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {section.items.map((item, iIdx) => (
                <CreditCard key={item.name} item={item} delay={sIdx * 0.05 + iIdx * 0.03} />
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-10 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-600">
        {t("ProofLayer's source code is public so anyone can see how verdicts are made. It is not open source: all rights reserved, and we do not accept outside contributions.")}
      </div>
    </div>
  );
}
