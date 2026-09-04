import { Link } from "react-router-dom";
import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, useMotionValue, useSpring, useTransform, useInView, animate } from "motion/react";
import {
  ScanLine, Eye, Film, AudioLines, Type, Sparkles,
  Brain, Fingerprint, History, SearchCheck, Globe, Users2,
  Gavel, Scale, GraduationCap, Layers, ShieldCheck,
} from "lucide-react";
import ShaderBackground from "../components/ui/ShaderBackground";
import client from "../api/client";
import { useAuthStore } from "../stores/authStore";

const TRIBUNAL_FALLBACK = "Tribunal 1.1";

const ANALYZERS = [
  { code: "01", name: "Metadata & Provenance", desc: "EXIF down to the capture sub-IFD, PNG generation parameters left by A1111 and ComfyUI, XMP, and C2PA Content Credentials. A declared trainedAlgorithmicMedia is the strongest single signal we have.", Icon: Fingerprint },
  { code: "02", name: "Error Level Analysis", desc: "Re-saves at fixed JPEG quality and looks for localised recompression outliers. Used honestly: it flags splicing and editing, it never votes on whether an image is AI.", Icon: ScanLine },
  { code: "03", name: "Community Forensics ViT", desc: "ViT-S/16 trained on 2.7M images from 4,803 generators. Runs on a native-resolution crop plus a global view, and its score is calibrated against twenty 2026 generators.", Icon: Brain },
  { code: "04", name: "Retrained Detector", desc: "The member that learns. Fine-tuned from the human review queue and our own labelled sets, so verdicts you correct today change the model tomorrow.", Icon: GraduationCap },
  { code: "05", name: "AI Ensemble", desc: "Two independent image classifiers behind a photographic-content gate, so screenshots and diagrams are not judged by models trained on photos.", Icon: Layers },
  { code: "06", name: "Vision LLM", desc: "A cautious forensic prompt. It must point to a concrete defect in this image - six fingers, impossible text, mismatched earrings - or it says nothing.", Icon: Eye },
  { code: "07", name: "Video Frame Sampler", desc: "Frames sampled across the whole clip, not the first eight seconds, each scored by the forensics ViT. The clip gets the median.", Icon: Film },
  { code: "08", name: "Audio Spectrogram", desc: "MFCC variance, spectral flatness, pitch, noise floor. Vocoder artifacts and synthetic-voice patterns raise flags and a probability.", Icon: AudioLines },
  { code: "09", name: "Text LLM", desc: "AI authorship from perplexity, sentence rhythm, and discourse markers.", Icon: Type },
];

const TRIBUNAL_RULES = [
  { Icon: Scale, title: "Weighted standing", body: "Every member's vote is weighted by measured reliability, not by guess. Members that failed the measurement were removed, not just turned down." },
  { Icon: ShieldCheck, title: "Calibrated on real photos", body: "Thresholds are set on the tail of real-photo scores across 210 originals, so lifting recall on new generators added zero false accusations." },
  { Icon: Gavel, title: "A split bench goes to a human", body: "When confident members disagree and the minority carries real weight, the case is escalated for review instead of averaged into a shrug." },
  { Icon: Fingerprint, title: "Every verdict is traceable", body: "Each result carries the Tribunal version and a fingerprint of the exact roster and weights that produced it." },
];

const FEATURES = [
  {
    Icon: History,
    title: "Results Archive",
    desc: "Every submission stored with full evidence. Browse, filter, re-examine.",
    accent: "text-signal-cyan",
  },
  {
    Icon: SearchCheck,
    title: "Fact-Check Engine",
    desc: "Cross-reference claims against live sources. Linked evidence per assertion.",
    accent: "text-signal-amber",
  },
  {
    Icon: Globe,
    title: "Provenance Trail",
    desc: "Reverse-image search and origin detection. Track publication history.",
    accent: "text-signal-violet",
  },
  {
    Icon: Users2,
    title: "Community Layer",
    desc: "Crowdsource votes alongside machine verdicts. Human signal where models disagree.",
    accent: "text-signal-sage",
  },
];

const NUMBERS = [
  { v: "09", l: "Active analyzers" },
  { v: "≈4s", l: "Median image verdict" },
  { v: "500MB", l: "Max upload" },
  { v: "REST", l: "Open API" },
];

const PRINCIPLES = [
  { kw: "Forensic", body: "Every submission treated like an evidence file. Crop marks. Case IDs. Provenance trails.", accent: "violet" },
  { kw: "Transparent", body: "No black-box scores. Each analyzer publishes raw JSON evidence alongside its verdict.", accent: "cyan" },
  { kw: "Skeptical", body: "If two methods disagree, we surface that. Inconclusive is a valid answer - not a failure.", accent: "amber" },
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
  const { data: statusData } = useQuery<{ services?: { analyzers?: { ensemble?: string } } }>({
    queryKey: ["system-status-ensemble"],
    queryFn: () => client.get("/system/status/").then((r) => r.data),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const tribunalLabel = statusData?.services?.analyzers?.ensemble || TRIBUNAL_FALLBACK;
  const user = useAuthStore((s) => s.user);
  const authedCta = user ? "/upload" : "/register";
  const authedLabel = user ? "Open Dashboard →" : "Begin Investigation →";

  return (
    <div className="min-h-screen text-ink-100 relative">
      <ShaderBackground variant="noir" />

      {/* HEADER */}
      <motion.header
        className="sticky top-0 z-30 backdrop-blur-xl bg-ink-950/80 border-b border-[var(--line)]"
        initial={{ y: -48, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-end gap-2">
            <span className="font-display text-[1.75rem] leading-none text-ink-50 tracking-tight">
              Proof<span className="italic text-iris">Layer</span>
            </span>
            <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-500 mb-1 hidden md:inline">
              / Forensic Lab
            </span>
          </Link>
          <div className="flex items-center gap-3">
            {user ? (
              <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-400 hidden md:inline">
                <span className="text-ink-600 mr-1.5">agent:</span>
                <span className="text-ink-200 truncate max-w-[180px] inline-block align-bottom">{user.email}</span>
              </span>
            ) : (
              <Link to="/login" className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500 hover:text-ink-100 transition-colors">
                Sign in
              </Link>
            )}
            <MagneticBtn to={authedCta} className="btn-forensic">
              {authedLabel}
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
            <span className="label-mono">Issue No. 042 · {new Date().toISOString().slice(0, 10)}</span>
            <span className="text-ink-700">·</span>
            <span className="label-mono signal-sage">LIVE</span>
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
                Is this image
                <br />
                <span className="italic text-iris">telling the truth</span>
                <span className="text-ink-50">?</span>
              </motion.h1>

              <motion.p
                variants={fadeUp}
                transition={{ duration: 0.6 }}
                className="mt-10 text-lg text-ink-200 max-w-xl leading-relaxed"
              >
                Forensic verification lab for synthetic media.
                Nine analyzers cross-examine every file and publish evidence, not just verdicts.
              </motion.p>

              <motion.div
                variants={fadeUp}
                transition={{ duration: 0.6 }}
                className="mt-10 flex flex-wrap items-center gap-3"
              >
                <MagneticBtn to={authedCta} className="btn-forensic group text-sm">
                  <span>Submit Evidence</span>
                  <motion.span
                    animate={{ x: [0, 4, 0] }}
                    transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                  >
                    →
                  </motion.span>
                </MagneticBtn>
                <a href="https://api.prooflayer.cloud/api/docs/" className="btn-ghost">
                  API Reference
                </a>
                <div className="flex items-center gap-2 ml-2 text-[11px] font-mono text-ink-500">
                  <span className="w-1.5 h-1.5 bg-signal-sage rounded-full pulse-dot" />
                  Free during beta
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
                <div className="case-card crop-marks p-7 relative">
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
                      <span className="label-mono">Sample Verdict</span>
                    </div>
                    <span className="badge text-signal-blood">SYNTHETIC</span>
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
                      { l: "CF-VIT", v: "fake", c: "text-signal-blood", n: "0.91" },
                      { l: "NPR-VIT", v: "fake", c: "text-signal-blood", n: "0.87" },
                      { l: "ELA", v: "suspicious", c: "text-signal-amber", n: "0.62" },
                      { l: "META", v: "stripped", c: "text-ink-400", n: "-" },
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
                          <span className={r.c}>{r.v}</span>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                  <div className="dot-divider mb-3" />
                  <div className="flex items-center justify-between font-mono text-[10px] text-ink-500">
                    <span>Aggregated · weighted ensemble</span>
                    <span className="signal-amber">Reviewed by humans</span>
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
          {NUMBERS.map((n) => (
            <motion.div
              key={n.l}
              variants={fadeUp}
              transition={{ duration: 0.6 }}
              whileHover={{ y: -3 }}
              className="group relative"
            >
              <div className="font-display text-6xl lg:text-7xl text-ink-50 leading-none ticker group-hover:text-iris transition-colors duration-500">{n.v}</div>
              <div className="label-mono mt-4">{n.l}</div>
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
                    className={`font-display text-6xl italic ${text} mb-5`}
                    variants={{ hover: { x: 5 } }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
                    {p.kw}.
                  </motion.div>
                  <p className="text-ink-300 leading-relaxed">{p.body}</p>
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
                Nine judges<span className="italic text-iris">,</span>
                <br />
                one verdict.
              </h2>
            </div>
            <p className="max-w-md text-ink-200 leading-relaxed">
              Tribunal is our own detection system: nine independent checks that each weigh the
              same evidence, a vote weighted by measured reliability - never a majority count -
              and a rule for when the bench is split enough that a human decides.
            </p>
          </motion.div>

          <motion.div
            className="grid sm:grid-cols-2 lg:grid-cols-4 gap-px bg-[var(--line-strong)] mb-14"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-50px" }}
            variants={{ visible: { transition: { staggerChildren: 0.06 } } }}
          >
            {TRIBUNAL_RULES.map((r) => {
              const Icon = r.Icon;
              return (
                <motion.div key={r.title} variants={fadeUp} transition={{ duration: 0.6 }} className="bg-[var(--bg)] p-6">
                  <div className="text-signal-amber/80 mb-4"><Icon size={18} strokeWidth={1.5} /></div>
                  <div className="font-display text-xl text-ink-50 leading-tight mb-2">{r.title}</div>
                  <p className="text-sm text-ink-300 leading-relaxed">{r.body}</p>
                </motion.div>
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
            {ANALYZERS.map((a, i) => {
              const Icon = a.Icon;
              return (
                <motion.div
                  key={a.code}
                  variants={fadeUp}
                  transition={{ duration: 0.6 }}
                  whileHover="hover"
                  className="grid grid-cols-[auto_auto_1fr] md:grid-cols-12 gap-3 md:gap-6 py-6 cursor-default group"
                >
                  <div className="font-mono text-xs text-ink-500 ticker pt-1 md:col-span-1">
                    {String(i + 1).padStart(2, "0")}
                  </div>
                  <motion.div
                    className="text-signal-amber/70 flex items-start pt-1 md:col-span-1"
                    variants={{ hover: { color: "var(--signal-amber)", scale: 1.15 } }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
                    <Icon size={18} strokeWidth={1.5} />
                  </motion.div>
                  <motion.div
                    className="font-display text-xl md:text-2xl lg:text-3xl text-ink-50 leading-tight md:col-span-4"
                    variants={{ hover: { x: 6 } }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
                    {a.name}
                  </motion.div>
                  <p className="col-span-3 md:col-span-6 text-sm text-ink-300 leading-relaxed mt-1 md:mt-0">{a.desc}</p>
                </motion.div>
              );
            })}
            <motion.div
              variants={fadeUp}
              transition={{ duration: 0.6 }}
              className="grid grid-cols-[auto_auto_1fr] md:grid-cols-12 gap-3 md:gap-6 py-6"
            >
              <div className="w-6 md:col-span-1" />
              <div className="text-signal-violet/70 flex items-start pt-1 md:col-span-1">
                <Sparkles size={18} strokeWidth={1.5} />
              </div>
              <div className="font-display text-xl md:text-2xl lg:text-3xl italic text-ink-300 leading-tight md:col-span-4">
                Measured, not assumed.
              </div>
              <div className="col-span-3 md:col-span-6 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500 pt-2 mt-1 md:mt-0">
                Every member is benchmarked on 2022 and 2026 generators before it gets a vote · retrain on Flux 2 and Sora 2 in progress
              </div>
            </motion.div>
          </motion.div>
        </section>

        {/* FEATURES BEYOND UPLOAD */}
        <section className="pb-28">
          <motion.div
            className="mb-14"
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <div className="label-mono mb-3 flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-signal-fuchsia rounded-full pulse-dot" />
              Beyond the Upload
            </div>
            <h2 className="font-display text-6xl lg:text-7xl text-ink-50 leading-[0.95]">
              A full <span className="italic text-iris">forensic</span>
              <br />
              workspace.
            </h2>
          </motion.div>

          <motion.div
            className="grid md:grid-cols-2 gap-px bg-[var(--line-strong)] border border-[var(--line-strong)]"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-50px" }}
            variants={{ visible: { transition: { staggerChildren: 0.1 } } }}
          >
            {FEATURES.map((f) => {
              const Icon = f.Icon;
              return (
                <motion.div
                  key={f.title}
                  variants={fadeUp}
                  transition={{ duration: 0.6 }}
                  whileHover="hover"
                  className="bg-ink-950 p-6 sm:p-8 group cursor-default"
                >
                  <motion.div
                    className={`${f.accent} mb-4`}
                    variants={{ hover: { scale: 1.1, x: 2 } }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
                    <Icon size={20} strokeWidth={1.5} />
                  </motion.div>
                  <motion.div
                    className="font-display text-3xl text-ink-50 mb-3"
                    variants={{ hover: { x: 4 } }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
                    {f.title}
                  </motion.div>
                  <p className="text-sm text-ink-300 leading-relaxed">{f.desc}</p>
                </motion.div>
              );
            })}
          </motion.div>
        </section>

        {/* EMBED WIDGET */}
        <section className="pb-28 grid lg:grid-cols-2 gap-14 items-center">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
          >
            <div className="label-mono mb-3 flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-signal-fuchsia rounded-full pulse-dot" />
              Embeddable
            </div>
            <h2 className="font-display text-6xl lg:text-7xl text-ink-50 leading-[0.95] mb-6">
              Drop a <span className="italic text-iris">badge</span>
              <br />
              on any page.
            </h2>
            <p className="text-ink-200 leading-relaxed max-w-md mb-8">
              One script tag. Real-time verdict fed by your submission's SHA-256.
              Public CORS, no API key required.
            </p>
            <MagneticBtn to={user ? "/embed" : "/register"} className="btn-forensic">
              {user ? "Open Embed →" : "Get Started →"}
            </MagneticBtn>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
            className="case-card crop-marks group overflow-hidden"
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--line)]">
              <span className="label-mono">embed.html</span>
              <div className="flex gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-signal-blood/40 group-hover:bg-signal-blood transition-colors" />
                <span className="w-2.5 h-2.5 rounded-full bg-signal-amber/40 group-hover:bg-signal-amber transition-colors" />
                <span className="w-2.5 h-2.5 rounded-full bg-signal-sage/40 group-hover:bg-signal-sage transition-colors" />
              </div>
            </div>
            <pre className="font-mono text-[13px] text-ink-100 p-6 leading-relaxed overflow-x-auto bg-ink-950/80">
<span className="text-ink-500">{"<!-- one line, anywhere -->"}</span>{"\n"}
<span className="text-signal-violet">{"<script"}</span> <span className="text-signal-cyan">src</span>=<span className="text-signal-amber">"https://prooflayer.cloud/widget.js"</span><span className="text-signal-violet">{"></script>"}</span>{"\n"}
<span className="text-signal-violet">{"<div"}</span> <span className="text-signal-cyan">data-prooflayer-sha256</span>=<span className="text-signal-amber">"7a3f2c..."</span><span className="text-signal-violet">{"></div>"}</span>
            </pre>
          </motion.div>
        </section>

        {/* CTA */}
        <section className="py-28 text-center relative overflow-hidden border-t border-[var(--line)]">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
          >
            <div className="label-mono mb-6">Begin</div>
            <h2 className="font-display text-7xl lg:text-[9rem] text-ink-50 leading-[0.85] tracking-tight">
              Question <span className="italic text-iris">everything</span>.
            </h2>
            <p className="text-ink-200 mt-8 max-w-md mx-auto leading-relaxed">
              Free during beta. Submit your first file in under thirty seconds.
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
            <span className="text-iris">Confidence ≠ Certainty</span>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <a href="/pricing" className="hover:text-signal-amber transition-colors">Pricing</a>
            <a href="https://api.prooflayer.cloud/api/docs/" className="hover:text-signal-amber transition-colors">API Docs</a>
            <a href="https://github.com/jeezdredd/prooflayer" className="hover:text-signal-amber transition-colors">Source</a>
            <a href="/terms" className="hover:text-ink-300 transition-colors">Terms</a>
            <a href="/privacy" className="hover:text-ink-300 transition-colors">Privacy</a>
            <a href="/refund" className="hover:text-ink-300 transition-colors">Refund Policy</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
