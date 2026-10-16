import { Link } from "react-router-dom";
import { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion, useMotionValue, useSpring, useTransform, useInView, animate } from "motion/react";
import {
  BadgeCheck,
  EyeOff,
  ScanLine, Eye, Film, AudioLines, Type, Sparkles,
  Brain, Fingerprint,
  Gavel, Scale, GraduationCap, Layers, ShieldCheck, Network, ShieldAlert,
} from "lucide-react";
import ShaderBackground from "../components/ui/ShaderBackground";
import type { BrainMember } from "../components/landing/TribunalBrain";
import Roadmap from "../components/landing/Roadmap";
import Workspace from "../components/landing/Workspace";
import client from "../api/client";
import { useAuthStore } from "../stores/authStore";
import LangSwitch from "../components/LangSwitch";
import { msg, t } from "../i18n";

const TribunalBrain = lazy(() => import("../components/landing/TribunalBrain"));

const TRIBUNAL_FALLBACK = "Tribunal 1.7.1";

const ANALYZERS: (BrainMember & { desc: string; Icon: typeof Brain })[] = [
  { code: "01", short: msg("Metadata"), kind: "provenance", name: msg("Metadata & Provenance"), tag: msg("C2PA · IPTC · hidden watermarks"), desc: msg("Reads the traces generators leave on purpose: C2PA Content Credentials checked against the official trust list (Google, Adobe, Microsoft and others), IPTC AI labels, the hidden watermarks of Stable Diffusion and FLUX, and generation settings left by A1111 and ComfyUI. A verified signature or a decoded watermark settles the case on its own; a damaged watermark or stripped credentials are reported as an attempt to hide AI traces."), Icon: Fingerprint },
  { code: "02", short: msg("ELA"), kind: "image", name: msg("Error Level Analysis"), tag: msg("splicing, not synthesis"), desc: msg("Re-saves at fixed JPEG quality and looks for localised recompression outliers. Flags splicing and editing; it never votes on whether an image is AI."), Icon: ScanLine },
  { code: "03", short: msg("Forensics ViT"), kind: "image", name: msg("Community Forensics ViT"), tag: msg("2.7M images · 4,803 generators"), desc: msg("ViT-S/16 trained on 2.7M images from 4,803 generators. Runs on a native-resolution crop plus a global view; its score is calibrated against twenty 2026 generators."), Icon: Brain },
  { code: "04", short: msg("Retrained"), kind: "image", name: msg("Retrained Detector"), tag: msg("weekly, gated retraining"), desc: msg("Retrains itself every week on fresh generator output and reviewed uploads. A new version goes live only if it beats the current one on a held-out set and calls no real photo AI; otherwise it is thrown away. Sees Flux 2, Sora 2 and GPT Image where the rest of the bench is blind."), Icon: GraduationCap },
  { code: "05", short: msg("CLIP Probe"), kind: "image", name: msg("CLIP Probe"), tag: msg("independent backbone"), desc: msg("A linear probe on CLIP embeddings, a different network from the forensics models, so when it agrees with them the agreement means something. Calibrated so real photos stay below the line."), Icon: Network },
  { code: "06", short: msg("AI Ensemble"), kind: "image", name: msg("AI Ensemble"), tag: msg("two classifiers, photo gate"), desc: msg("Two independent image classifiers behind a photographic-content gate, so screenshots and diagrams are not judged by models trained on photos."), Icon: Layers },
  { code: "07", short: msg("Vision LLM"), kind: "image", name: msg("Vision LLM"), tag: msg("must name the defect"), desc: msg("A cautious forensic prompt on our own GPU, about six seconds an image. It must point to a concrete defect in this image - six fingers, impossible text, mismatched earrings - or it says nothing."), Icon: Eye },
  { code: "08", short: msg("Video"), kind: "video", name: msg("Video Frame Sampler"), tag: msg("whole clip, median verdict"), desc: msg("Frames sampled across the whole clip, not the first eight seconds, each scored by the forensics ViT. The clip gets the median."), Icon: Film },
  { code: "09", short: msg("Audio"), kind: "audio", name: msg("Audio Spectrogram"), tag: msg("vocoder artifacts"), desc: msg("MFCC variance, spectral flatness, pitch, noise floor. Vocoder artifacts and synthetic-voice patterns raise flags and a probability."), Icon: AudioLines },
  { code: "10", short: msg("Text Classifier"), kind: "text", name: msg("Text Classifier"), tag: msg("trained on ru · en · fr"), desc: msg("A multilingual encoder fine-tuned on human essays, pre-2022 Wikipedia and fresh writing from current open models, humanized rewrites included. On held-out text it flags 91-100% of machine writing and 2-4% of human essays, and marks the passages that read most machine-like. Alone it can only raise a flag, never convict. Reads PDF and DOCX too."), Icon: Type },
  { code: "11", short: msg("Anti-bypass"), kind: "text", name: msg("Anti-bypass"), tag: msg("humanizer tricks · hidden text"), desc: msg("Catches the tricks AI humanizers use: Latin letters hidden inside Cyrillic words and the reverse, look-alike punctuation, stray accents, styled letters, invisible characters, odd spaces, and DOCX text that is hidden, white or 1pt. Silent unless it finds a trick; when it does, the result says plainly that someone tried to hide AI traces."), Icon: ShieldAlert },
];

const TRIBUNAL_RULES = [
  { Icon: Scale, title: msg("Weighted standing"), body: msg("Every member's vote is weighted by measured reliability, not by guess. Members that failed the measurement were removed.") },
  { Icon: ShieldCheck, title: msg("Calibrated on real photos"), body: msg("Thresholds are set on the tail of real-photo scores across hundreds of originals, so lifting recall on new generators added zero false accusations.") },
  { Icon: Gavel, title: msg("Split bench goes to a human"), body: msg("When confident members disagree and the minority carries real weight, the case is escalated for review instead of averaged into a shrug.") },
  { Icon: Fingerprint, title: msg("Every verdict is traceable"), body: msg("Each result carries the Tribunal version and a fingerprint of the exact roster and weights that produced it.") },
  { Icon: BadgeCheck, title: msg("Proof outranks votes"), body: msg("A verified Content Credentials signature or a decoded generator watermark settles the case on its own, whatever the detectors say.") },
  { Icon: EyeOff, title: msg("Hiding traces is a trace"), body: msg("Damaged watermarks, cut-out credentials and disguised characters are named in the result as an attempt to hide AI traces.") },
];


const NUMBERS = [
  { k: "checks", v: "11", l: msg("Active analyzers"), small: false },
  { k: "kinds", v: msg("Photo · video · voice · text"), l: msg("Checked in one place"), small: true },
  { k: "generators", v: "20+", l: msg("AI models we catch in text, photos, video and voice: ChatGPT, Gemini, Midjourney, Sora and more"), small: false },
  { k: "accuracy", v: msg("99.7%"), l: msg("Accuracy telling AI from real photos"), small: false },
];

const PRINCIPLES = [
  { kw: msg("Forensic"), body: msg("Every submission treated like an evidence file. Crop marks. Case IDs. Provenance trails."), accent: "violet" },
  { kw: msg("Transparent"), body: msg("No black-box scores. Each analyzer publishes raw JSON evidence alongside its verdict."), accent: "cyan" },
  { kw: msg("Skeptical"), body: msg("If two methods disagree, we surface that. Inconclusive is a valid answer - not a failure."), accent: "amber" },
];

function CountUp({ value, suffix = "" }: { value: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });
  const mv = useMotionValue(0);
  const rounded = useTransform(mv, (v) => Math.round(v));
  useEffect(() => {
    if (inView) {
      const controls = animate(mv, value, { duration: 1.6, ease: [0.16, 1, 0.3, 1] });
      return () => controls.stop();
    }
  }, [inView, value, mv]);
  return (
    <span ref={ref} className="ticker">
      <motion.span>{rounded}</motion.span>
      {suffix}
    </span>
  );
}

function TiltCard({ children }: { children: React.ReactNode }) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotateX = useSpring(useTransform(y, [-0.5, 0.5], [6, -6]), { stiffness: 200, damping: 22 });
  const rotateY = useSpring(useTransform(x, [-0.5, 0.5], [-6, 6]), { stiffness: 200, damping: 22 });

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    x.set((e.clientX - rect.left) / rect.width - 0.5);
    y.set((e.clientY - rect.top) / rect.height - 0.5);
  };
  const onLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.div
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{ rotateX, rotateY, transformStyle: "preserve-3d", perspective: 1500 }}
      className="will-change-transform"
    >
      {children}
    </motion.div>
  );
}

function MagneticBtn({ children, ...rest }: React.ComponentProps<typeof Link>) {
  const ref = useRef<HTMLAnchorElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 300, damping: 22 });
  const sy = useSpring(y, { stiffness: 300, damping: 22 });

  const onMove = (e: React.MouseEvent) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    x.set((e.clientX - rect.left - rect.width / 2) * 0.2);
    y.set((e.clientY - rect.top - rect.height / 2) * 0.2);
  };
  const onLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.span style={{ x: sx, y: sy }} onMouseMove={onMove} onMouseLeave={onLeave} className="inline-block">
      <Link ref={ref} {...rest}>
        {children}
      </Link>
    </motion.span>
  );
}

const fadeUp = {
  hidden: { opacity: 0, y: 20, filter: "blur(6px)" },
  visible: { opacity: 1, y: 0, filter: "blur(0px)" },
};

export default function LandingPage() {
  const { data: statusData } = useQuery<{ services?: { analyzers?: { ensemble?: string } }; verdict_timing?: { image_median_s: number | null; samples: number } }>({
    queryKey: ["system-status-ensemble"],
    queryFn: () => client.get("/system/status/").then((r) => r.data),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const tribunalLabel = statusData?.services?.analyzers?.ensemble || TRIBUNAL_FALLBACK;
  const numbers = NUMBERS;
  const analyzers = useMemo(() => ANALYZERS.map((a) => ({ ...a, short: t(a.short), name: t(a.name), tag: t(a.tag), desc: t(a.desc) })), []);
  const [openRule, setOpenRule] = useState<number | null>(null);
  const [openCheck, setOpenCheck] = useState<string | null>(null);
  const user = useAuthStore((s) => s.user);
  const authedCta = user ? "/upload" : "/register";
  const authedLabel = user ? `${t("Open Dashboard")} →` : `${t("Begin Investigation")} →`;

  return (
    <div className="min-h-screen text-ink-100 relative">
      <ShaderBackground variant="noir" />

      {/* HEADER */}
      <motion.header
        className="sticky top-0 z-30 backdrop-blur-xl bg-ink-950/30 border-b border-white/5"
        initial={{ y: -48, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10 h-20 flex items-center justify-between gap-6">
          <Link to="/" className="flex items-end gap-2">
            <span className="font-display text-[1.75rem] leading-none text-ink-50 tracking-tight">
              Proof<span className="italic text-iris">Layer</span>
            </span>
            <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-500 mb-1 hidden md:inline">
              / {t("Forensic Lab")}
            </span>
          </Link>
          <div className="flex items-center gap-5">
            <LangSwitch />
            {user ? (
              <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-400 hidden md:inline">
                <span className="text-ink-600 mr-1.5">{t("agent:")}</span>
                <span className="text-ink-200 truncate max-w-[180px] inline-block align-bottom">{user.email}</span>
              </span>
            ) : (
              <Link to="/login" className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500 hover:text-ink-100 transition-colors">
                {t("Sign in")}
              </Link>
            )}
            <MagneticBtn to={authedCta} className="btn-forensic">
              <span className="sm:hidden">{user ? `${t("Dashboard")} →` : `${t("Start")} →`}</span>
              <span className="hidden sm:inline">{authedLabel}</span>
            </MagneticBtn>
          </div>
        </div>
      </motion.header>

      <main className="max-w-[1280px] mx-auto px-6 lg:px-10 relative z-10">
        {/* HERO */}
        <section className="pt-20 pb-24">
          <motion.div
            className="flex items-center gap-3 mb-12"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <span className="relative inline-flex">
              <span className="w-1.5 h-1.5 bg-signal-amber rounded-full" />
              <motion.span
                className="absolute inset-0 bg-signal-amber rounded-full"
                animate={{ scale: [1, 2.4], opacity: [0.7, 0] }}
                transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
              />
            </span>
            <span className="label-mono">{t("Issue No. 042")} · {new Date().toISOString().slice(0, 10)}</span>
            <span className="text-ink-700">·</span>
            <span className="label-mono signal-sage">{t("LIVE")}</span>
          </motion.div>

          <div className="grid lg:grid-cols-12 gap-14 items-start">
            <motion.div
              className="lg:col-span-7"
              initial="hidden"
              animate="visible"
              variants={{ visible: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } } }}
            >
              <motion.h1
                variants={fadeUp}
                transition={{ duration: 0.7 }}
                className="font-display text-[clamp(3rem,8vw,7.5rem)] leading-[0.92] tracking-[-0.025em] text-ink-50"
              >
                {t("Is this image")}
                <br />
                <span className="italic text-iris">{t("telling the truth")}</span>
                <span className="text-ink-50">?</span>
              </motion.h1>

              <motion.p
                variants={fadeUp}
                transition={{ duration: 0.6 }}
                className="mt-10 text-lg text-ink-200 max-w-xl leading-relaxed"
              >
                {t("Forensic verification lab for synthetic media. Eleven analyzers cross-examine every file and publish evidence, not just verdicts.")}
              </motion.p>

              <motion.div
                variants={fadeUp}
                transition={{ duration: 0.6 }}
                className="mt-12 flex flex-wrap items-center gap-4"
              >
                <MagneticBtn to={authedCta} className="btn-forensic group text-sm">
                  <span>{t("Submit Evidence")}</span>
                  <motion.span
                    animate={{ x: [0, 4, 0] }}
                    transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                  >
                    →
                  </motion.span>
                </MagneticBtn>
                <a href="https://api.prooflayer.cloud/api/docs/" className="btn-ghost">
                  {t("API Reference")}
                </a>
                <div className="flex items-center gap-2 ml-3 text-[11px] font-mono text-ink-500">
                  <span className="w-1.5 h-1.5 bg-signal-sage rounded-full pulse-dot" />
                  {t("Free plan, no card")}
                </div>
              </motion.div>
            </motion.div>

            {/* SAMPLE VERDICT */}
            <motion.aside
              className="lg:col-span-5"
              initial={{ opacity: 0, y: 30, filter: "blur(10px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0)" }}
              transition={{ duration: 0.8, delay: 0.25, ease: [0.16, 1, 0.3, 1] }}
            >
              <TiltCard>
                <div className="case-card crop-marks p-8 relative">
                  <div className="flex items-center justify-between mb-5">
                    <div className="flex items-center gap-2">
                      <span className="relative inline-flex">
                        <span className="w-1.5 h-1.5 bg-signal-cyan rounded-full" />
                        <motion.span
                          className="absolute inset-0 bg-signal-cyan rounded-full"
                          animate={{ scale: [1, 2.4], opacity: [0.7, 0] }}
                          transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
                        />
                      </span>
                      <span className="label-mono">{t("Sample Verdict")}</span>
                    </div>
                    <span className="badge text-signal-blood">{t("SYNTHETIC")}</span>
                  </div>

                  <div className="font-mono text-[10px] text-ink-500 mb-3 ticker">
                    CASE/2026-0507 · img_4232.png · SHA 7a3f2c…b91d4e
                  </div>

                  <div className="flex items-end gap-3 mb-6">
                    <div className="font-display text-[6.5rem] leading-none text-signal-blood ticker">
                      <CountUp value={87} />
                    </div>
                    <div className="font-display text-3xl text-ink-500 mb-3">%</div>
                  </div>

                  <div className="space-y-2.5 mb-5">
                    {[
                      { l: "CF-VIT", v: msg("fake"), c: "text-signal-blood", n: "0.91" },
                      { l: "CLIP", v: msg("fake"), c: "text-signal-blood", n: "0.87" },
                      { l: "ELA", v: msg("suspicious"), c: "text-signal-amber", n: "0.62" },
                      { l: "META", v: msg("stripped"), c: "text-ink-400", n: "-" },
                    ].map((r, i) => (
                      <motion.div
                        key={r.l}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.55 + i * 0.1, duration: 0.4 }}
                        className="flex justify-between items-center font-mono text-[10px] uppercase tracking-[0.14em]"
                      >
                        <span className="text-ink-500">{r.l}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-ink-600 ticker">{r.n}</span>
                          <span className={r.c}>{t(r.v)}</span>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                  <div className="dot-divider mb-3" />
                  <div className="flex items-center justify-between font-mono text-[10px] text-ink-500">
                    <span>{t("Aggregated · weighted ensemble")}</span>
                    <span className="signal-amber">{t("Split cases go to a human")}</span>
                  </div>
                </div>
              </TiltCard>
            </motion.aside>
          </div>
        </section>

        {/* NUMBERS STRIP */}
        <motion.div
          className="mt-24 grid grid-cols-2 md:grid-cols-4 gap-x-10 gap-y-10"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
          variants={{ visible: { transition: { staggerChildren: 0.08 } } }}
        >
          {numbers.map((n) => (
            <motion.div
              key={n.k}
              variants={fadeUp}
              transition={{ duration: 0.6 }}
              whileHover={{ y: -3 }}
              className="group relative"
            >
              <div className={`font-display ${n.small ? "text-4xl lg:text-5xl" : "text-6xl lg:text-7xl"} text-ink-50 leading-none ticker group-hover:text-iris transition-colors duration-500`}>{t(n.v).replace(/ · /g, "\u00a0· ")}</div>
              <div className="label-mono mt-4">{t(n.l)}</div>
            </motion.div>
          ))}
        </motion.div>

        {/* PRINCIPLES */}
        <section className="py-28">
          <motion.div
            className="grid md:grid-cols-3 gap-x-10 gap-y-12"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={{ visible: { transition: { staggerChildren: 0.12 } } }}
          >
            {PRINCIPLES.map((p, i) => {
              const text =
                p.accent === "violet" ? "text-signal-violet" :
                p.accent === "cyan" ? "text-signal-cyan" :
                "text-signal-amber";
              return (
                <motion.div
                  key={p.kw}
                  variants={fadeUp}
                  transition={{ duration: 0.7 }}
                  whileHover="hover"
                  className="relative group"
                >
                  <div className="hairline mb-6" />
                  <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-4 ticker">
                    {String(i + 1).padStart(2, "0")} / 03
                  </div>
                  <motion.div
                    className={`font-display text-5xl xl:text-6xl italic ${text} mb-5 break-words`}
                    variants={{ hover: { x: 5 } }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
                    {t(p.kw)}.
                  </motion.div>
                  <p className="text-ink-300 leading-relaxed">{t(p.body)}</p>
                </motion.div>
              );
            })}
          </motion.div>
        </section>

        {/* TRIBUNAL */}
        <section className="pb-28" id="tribunal">
          <motion.div
            className="flex items-end justify-between mb-10 flex-wrap gap-6"
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <div>
              <div className="label-mono mb-3 flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-signal-cyan rounded-full pulse-dot" />
                {tribunalLabel}
              </div>
              <h2 className="font-display text-6xl lg:text-7xl text-ink-50 leading-[0.95]">
                {t("Eleven judges")}<span className="italic text-iris">,</span>
                <br />
                {t("one verdict.")}
              </h2>
            </div>
            <p className="max-w-md text-ink-200 leading-relaxed">
              {t("Our own detection system. Eleven independent checks fire into one weighted vote, and a human takes over when the bench is split.")}
              <span className="block mt-2 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500">{t("point at or tap a neuron to see what it checks")}</span>
            </p>
          </motion.div>

          <motion.div
            className="mb-14"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
          >
            <Suspense fallback={<div className="aspect-[4/5] md:aspect-[16/9]" />}>
              <TribunalBrain
                members={analyzers}
                activeCode={openCheck}
                verdictLabel={tribunalLabel}
                onSelect={(code) => {
                  setOpenCheck(code);
                  requestAnimationFrame(() =>
                    document.getElementById(`judge-${code}`)?.scrollIntoView({ behavior: "smooth", block: "center" }),
                  );
                }}
              />
            </Suspense>
          </motion.div>

          <motion.div
            className="grid grid-cols-2 lg:grid-cols-3 gap-px bg-[var(--line)] mb-14 rounded-2xl overflow-hidden border border-[var(--line)]"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-50px" }}
            variants={{ visible: { transition: { staggerChildren: 0.06 } } }}
          >
            {TRIBUNAL_RULES.map((r, i) => {
              const Icon = r.Icon;
              const open = openRule === i;
              return (
                <motion.button
                  type="button"
                  key={r.title}
                  variants={fadeUp}
                  transition={{ duration: 0.6 }}
                  onClick={() => setOpenRule(open ? null : i)}
                  aria-expanded={open}
                  className="rounded-none bg-ink-950 p-5 text-left group hover:bg-ink-900 transition-colors"
                >
                  <motion.div
                    className="text-signal-amber/80 mb-4 inline-flex"
                    animate={{ scale: open ? 1.15 : 1, color: open ? "var(--signal-amber)" : undefined }}
                    whileHover={{ scale: 1.12, y: -2 }}
                    transition={{ type: "spring", stiffness: 260, damping: 18 }}
                  >
                    <Icon size={22} strokeWidth={1.5} />
                  </motion.div>
                  <div className="font-display text-lg lg:text-xl text-ink-50 leading-tight">{t(r.title)}</div>
                  <AnimatePresence initial={false}>
                    {open && (
                      <motion.p
                        key="body"
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25 }}
                        className="text-sm text-ink-300 leading-relaxed overflow-hidden pt-2"
                      >
                        {t(r.body)}
                      </motion.p>
                    )}
                  </AnimatePresence>
                </motion.button>
              );
            })}
          </motion.div>

          <motion.div
            className="divide-y divide-[var(--line-strong)]"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-50px" }}
            variants={{ visible: { transition: { staggerChildren: 0.05 } } }}
          >
            {analyzers.map((a, i) => {
              const Icon = a.Icon;
              const open = openCheck === a.code;
              return (
                <motion.div key={a.code} id={`judge-${a.code}`} variants={fadeUp} transition={{ duration: 0.6 }} className="scroll-mt-24">
                  <button
                    type="button"
                    onClick={() => setOpenCheck(open ? null : a.code)}
                    aria-expanded={open}
                    className="w-full grid grid-cols-[auto_auto_1fr] md:grid-cols-12 items-center gap-3 md:gap-6 py-4 text-left group"
                  >
                    <div className="font-mono text-xs text-ink-500 ticker md:col-span-1">
                      {String(i + 1).padStart(2, "0")}
                    </div>
                    <motion.div
                      className="text-signal-amber/70 group-hover:text-signal-amber inline-flex md:col-span-1"
                      animate={{ scale: open ? 1.2 : 1, rotate: open ? -8 : 0 }}
                      whileHover={{ scale: 1.15 }}
                      transition={{ type: "spring", stiffness: 260, damping: 18 }}
                    >
                      <Icon size={18} strokeWidth={1.5} />
                    </motion.div>
                    <div className="md:col-span-5 font-display text-xl md:text-2xl text-ink-50 leading-tight group-hover:translate-x-1 transition-transform">
                      {a.name}
                    </div>
                    <div className="col-span-3 md:col-span-5 flex items-center justify-between gap-4 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500">
                      <span>{a.tag}</span>
                      <motion.span animate={{ rotate: open ? 45 : 0 }} transition={{ type: "spring", stiffness: 300, damping: 20 }} className="text-ink-600 text-base leading-none">+</motion.span>
                    </div>
                  </button>
                  <AnimatePresence initial={false}>
                    {open && (
                      <motion.p
                        key="desc"
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25 }}
                        className="overflow-hidden md:pl-[calc(16.666%+1.5rem)] pb-5 text-sm text-ink-300 leading-relaxed max-w-2xl"
                      >
                        {a.desc}
                      </motion.p>
                    )}
                  </AnimatePresence>
                </motion.div>
              );
            })}
            <motion.div
              variants={fadeUp}
              transition={{ duration: 0.6 }}
              className="grid grid-cols-[auto_auto_1fr] md:grid-cols-12 items-center gap-3 md:gap-6 py-4"
            >
              <div className="w-6 md:col-span-1" />
              <div className="text-signal-violet/70 inline-flex md:col-span-1">
                <Sparkles size={18} strokeWidth={1.5} />
              </div>
              <div className="font-display text-xl md:text-2xl italic text-ink-300 leading-tight md:col-span-5">
                {t("Measured, not assumed.")}
              </div>
              <div className="col-span-3 md:col-span-5 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500">
                {t("benchmarked on 2022 and 2026 generators before it gets a vote")}
              </div>
            </motion.div>
          </motion.div>
        </section>

        {/* FEATURES BEYOND UPLOAD */}
        <section className="pb-28">
          <motion.div
            className="mb-10"
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <div className="label-mono mb-3 flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-signal-fuchsia rounded-full pulse-dot" />
              {t("Beyond the Upload")}
            </div>
            <div className="flex items-end justify-between flex-wrap gap-6">
              <h2 className="font-display text-6xl lg:text-7xl text-ink-50 leading-[0.95]">
                {t("A full")} <span className="italic text-iris">{t("forensic")}</span>
                <br />
                {t("workspace.")}
              </h2>
              <p className="max-w-md text-ink-200 leading-relaxed">
                {t("The verdict is where the work starts. Pick who you are and see what you get after the upload.")}
              </p>
            </div>
          </motion.div>

          <Workspace />
        </section>

        <Roadmap />

        {/* CTA */}
        <section className="py-28 text-center relative overflow-hidden border-t border-[var(--line)]">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
          >
            <div className="label-mono mb-6">{t("Begin")}</div>
            <h2 className="font-display text-7xl lg:text-[9rem] text-ink-50 leading-[0.85] tracking-tight">
              {t("Question")} <span className="italic text-iris">{t("everything")}</span>.
            </h2>
            <p className="text-ink-200 mt-8 max-w-md mx-auto leading-relaxed">
              {t("Start on the free plan, no card needed. Schools and universities: see Classroom pricing.")}
            </p>
            <div className="mt-12">
              <MagneticBtn to={authedCta} className="btn-forensic inline-flex text-sm">
                {authedLabel}
              </MagneticBtn>
            </div>
          </motion.div>
        </section>
      </main>

      <footer className="border-t border-[var(--line)] py-8 relative z-10">
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <span>© ProofLayer Lab - {new Date().getFullYear()}</span>
            <span className="text-iris">{t("Confidence ≠ Certainty")}</span>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <a href="/pricing" className="hover:text-signal-amber transition-colors">{t("Pricing")}</a>
            <a href="/changelog" className="hover:text-signal-amber transition-colors">{t("What's new")}</a>
            <a href="https://api.prooflayer.cloud/api/docs/" className="hover:text-signal-amber transition-colors">{t("API Docs")}</a>
            <a href="https://github.com/jeezdredd/prooflayer" className="hover:text-signal-amber transition-colors" title={t("Public for transparency; all rights reserved")}>{t("Source (view only)")}</a>
            <a href="/terms" className="hover:text-ink-300 transition-colors">{t("Terms")}</a>
            <a href="/privacy" className="hover:text-ink-300 transition-colors">{t("Privacy")}</a>
            <a href="/refund" className="hover:text-ink-300 transition-colors">{t("Refund Policy")}</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
