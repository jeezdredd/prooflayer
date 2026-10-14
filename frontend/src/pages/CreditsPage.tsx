import { motion } from "motion/react";
import { ExternalLink } from "lucide-react";
import { msg, t } from "../i18n";

interface Tech {
  name: string;
  href: string;
  note: string;
  icon?: string;
  license?: string;
}

const INTERFACE: Tech[] = [
  { name: "React 18", href: "https://react.dev", note: msg("Interface components"), icon: "react" },
  { name: "TypeScript 5", href: "https://www.typescriptlang.org", note: msg("Typed frontend code"), icon: "typescript" },
  { name: "Vite 6", href: "https://vite.dev", note: msg("Build and dev server"), icon: "vite" },
  { name: "React Router 7", href: "https://reactrouter.com", note: msg("Pages and navigation"), icon: "reactrouter" },
  { name: "Tailwind CSS 3", href: "https://tailwindcss.com", note: msg("Styling"), icon: "tailwindcss" },
  { name: "Motion", href: "https://motion.dev", note: msg("Animations"), icon: "framer" },
  { name: "Three.js", href: "https://threejs.org", note: msg("3D Tribunal brain on the landing page"), icon: "threedotjs" },
  { name: "Paper Shaders", href: "https://shaders.paper.design", note: msg("Animated backgrounds") },
  { name: "TanStack Query 5", href: "https://tanstack.com/query", note: msg("Loading and caching server data"), icon: "reactquery" },
  { name: "Zustand 5", href: "https://github.com/pmndrs/zustand", note: msg("Sign-in and language state") },
  { name: "Lucide", href: "https://lucide.dev", note: msg("Icons"), icon: "lucide" },
];

const SERVER: Tech[] = [
  { name: "Python 3.12", href: "https://www.python.org", note: msg("Backend language"), icon: "python" },
  { name: "Django 5.1", href: "https://www.djangoproject.com", note: msg("Web framework and admin"), icon: "django" },
  { name: "Django REST Framework", href: "https://www.django-rest-framework.org", note: msg("REST API, JWT sign-in, OpenAPI schema") },
  { name: "Celery 5.4", href: "https://docs.celeryq.dev", note: msg("Background analysis queue"), icon: "celery" },
  { name: "Redis 7.4", href: "https://redis.io", note: msg("Queue broker and cache"), icon: "redis" },
  { name: "PostgreSQL 16 + pgvector", href: "https://github.com/pgvector/pgvector", note: msg("Database and vector search for originality and provenance"), icon: "postgresql" },
  { name: "Django Channels + Daphne", href: "https://channels.readthedocs.io", note: msg("Live analysis progress over WebSocket") },
  { name: "MinIO", href: "https://min.io", note: msg("S3-compatible file storage"), icon: "minio" },
  { name: "WeasyPrint", href: "https://weasyprint.org", note: msg("PDF reports") },
  { name: "Unfold", href: "https://unfoldadmin.com", note: msg("Admin panel") },
];

const MODELS: Tech[] = [
  { name: "Community Forensics ViT-S/16", href: "https://huggingface.co/buildborderless/CommunityForensics-DeepfakeDet-ViT", note: msg("Main image detector, 2.7M images from 4,803 generators (NeurIPS 2024)"), icon: "huggingface", license: "Apache-2.0" },
  { name: "ProofLayer Detector", href: "https://huggingface.co/buildborderless/CommunityForensics-DeepfakeDet-ViT", note: msg("Our detector, fine-tuned from Community Forensics on reviewed uploads and new generators"), icon: "huggingface" },
  { name: "CLIP ViT-B/32", href: "https://huggingface.co/openai/clip-vit-base-patch32", note: msg("Independent backbone for our CLIP probe and image similarity"), icon: "huggingface", license: "MIT" },
  { name: "dima806/ai_vs_real_image_detection", href: "https://huggingface.co/dima806/ai_vs_real_image_detection", note: msg("Image ensemble member"), icon: "huggingface" },
  { name: "umm-maybe/AI-image-detector", href: "https://huggingface.co/umm-maybe/AI-image-detector", note: msg("Image ensemble member"), icon: "huggingface" },
  { name: "multilingual-e5-small", href: "https://huggingface.co/intfloat/multilingual-e5-small", note: msg("Base of our text classifier and the meaning search in the originality check"), icon: "huggingface", license: "MIT" },
  { name: "Qwen2.5-VL 7B", href: "https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct", note: msg("Vision model that must name a concrete defect"), icon: "ollama", license: "Apache-2.0" },
  { name: "Qwen2.5 3B", href: "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct", note: msg("Fact-check reasoning and AI answers for the assignment shadow"), icon: "ollama", license: "Apache-2.0" },
  { name: "PyTorch + Transformers", href: "https://huggingface.co/docs/transformers", note: msg("Running and training the models"), icon: "pytorch" },
  { name: "Ollama", href: "https://ollama.com", note: msg("Local language model server on our own GPU"), icon: "ollama" },
];

const TEXT: Tech[] = [
  { name: "spaCy", href: "https://spacy.io", note: msg("Claim extraction for fact-check"), icon: "spacy", license: "MIT" },
  { name: "wordfreq", href: "https://github.com/rspeer/wordfreq", note: msg("Word rarity for the age fit check") },
  { name: "Trafilatura", href: "https://trafilatura.readthedocs.io", note: msg("Article text from web pages") },
  { name: "pypdf + python-docx", href: "https://pypdf.readthedocs.io", note: msg("Text and hidden runs from PDF and DOCX") },
  { name: "SearXNG", href: "https://docs.searxng.org", note: msg("Self-hosted web search for the originality check") },
  { name: "Pillow + OpenCV", href: "https://opencv.org", note: msg("Image and video frame processing"), icon: "opencv" },
  { name: "imagehash + PDQ", href: "https://github.com/facebook/ThreatExchange/tree/main/pdq", note: msg("Perceptual hashes for re-uploads and known fakes") },
  { name: "librosa", href: "https://librosa.org", note: msg("Audio features") },
];

const INFRA: Tech[] = [
  { name: "Docker Compose", href: "https://docs.docker.com/compose/", note: msg("Every service runs in its own container"), icon: "docker" },
  { name: "Caddy", href: "https://caddyserver.com", note: msg("Web server and TLS"), icon: "caddy" },
  { name: "Cloudflare", href: "https://www.cloudflare.com", note: msg("DNS, tunnel and DDoS protection"), icon: "cloudflare" },
  { name: "Tailscale", href: "https://tailscale.com", note: msg("Private network for server access"), icon: "tailscale" },
  { name: "AMD ROCm", href: "https://www.amd.com/en/products/software/rocm.html", note: msg("GPU for the language models"), icon: "amd" },
  { name: "Paddle", href: "https://www.paddle.com", note: msg("Payments and invoices"), icon: "paddle" },
  { name: "Resend", href: "https://resend.com", note: msg("Transactional email"), icon: "resend" },
];

const DATA: Tech[] = [
  { name: "OpenFake", href: "https://huggingface.co/datasets/ComplexDataLab/OpenFake", note: msg("Real photos and images from current generators for training and testing"), icon: "huggingface" },
  { name: "CoAT", href: "https://huggingface.co/datasets/RussianNLP/coat", note: msg("Russian texts written by people and by models"), icon: "huggingface", license: "Apache-2.0" },
  { name: "DAIGT", href: "https://www.kaggle.com/datasets/thedrcat/daigt-v2-train-dataset", note: msg("English student essays and their AI counterparts"), icon: "kaggle" },
  { name: "Wikipedia", href: "https://www.wikipedia.org", note: msg("Human-written reference texts in ru, en and fr from before 2022"), icon: "wikipedia", license: "CC BY-SA" },
];

const SECTIONS: { label: string; items: Tech[] }[] = [
  { label: msg("Interface"), items: INTERFACE },
  { label: msg("Server"), items: SERVER },
  { label: msg("Detection models"), items: MODELS },
  { label: msg("Text, documents and media"), items: TEXT },
  { label: msg("Infrastructure and services"), items: INFRA },
  { label: msg("Data we train and measure on"), items: DATA },
];

function TechCard({ item, delay }: { item: Tech; delay: number }) {
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
        <div className="flex items-center gap-2.5 min-w-0">
          {item.icon && (
            <img
              src={`https://cdn.simpleicons.org/${item.icon}`}
              alt=""
              className="w-4 h-4 opacity-70 group-hover:opacity-100 transition-opacity"
              loading="lazy"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          )}
          <span className="text-sm text-ink-50 leading-tight break-words">{item.name}</span>
        </div>
        <ExternalLink size={12} strokeWidth={1.5} className="text-ink-600 group-hover:text-signal-amber transition-colors mt-0.5 shrink-0" />
      </div>
      <p className="text-xs text-ink-400 leading-relaxed">{t(item.note)}</p>
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
          {t("Stack")}
        </div>
        <h1 className="font-display text-5xl lg:text-6xl text-ink-50 leading-none">
          {t("What ProofLayer runs on")}
        </h1>
        <p className="text-ink-300 mt-3 max-w-xl leading-relaxed">
          {t("The technologies, models and data behind every check. All models run on our own servers; the services listed under infrastructure handle delivery, payments and email.")}
        </p>
      </motion.div>

      <div className="mt-12 space-y-10">
        {SECTIONS.map((section, sIdx) => (
          <div key={section.label}>
            <div className="label-mono mb-4">{t(section.label)}</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {section.items.map((item, iIdx) => (
                <TechCard key={item.name} item={item} delay={sIdx * 0.05 + iIdx * 0.03} />
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
