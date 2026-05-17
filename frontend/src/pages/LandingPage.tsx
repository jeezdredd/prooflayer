import { Link } from "react-router-dom";
import { useEffect, useRef } from "react";
import { motion, useMotionValue, useSpring, useTransform, useInView, animate } from "motion/react";
import { Tag, ScanLine, Cpu, Eye, Film, AudioLines, Type, Sparkles } from "lucide-react";
import ShaderBackground from "../components/ui/ShaderBackground";
import { useAuthStore } from "../stores/authStore";

const ANALYZERS = [
  { code: "01", name: "Metadata · EXIF", desc: "Reads camera signatures, editing-tool fingerprints, GPS, timestamp drift.", Icon: Tag },
  { code: "02", name: "Error Level Analysis", desc: "Re-saves at fixed JPEG quality, surfaces splice and paste regions.", Icon: ScanLine },
  { code: "03", name: "AI Image Ensemble", desc: "Three independent classifiers vote on synthetic likelihood.", Icon: Cpu },
  { code: "04", name: "Vision LLM", desc: "Multimodal model examines lighting, texture, fingers, eyes, uncanny valley.", Icon: Eye },
  { code: "05", name: "Video Frame Sampler", desc: "Uniform-interval frames pass through ELA + AI ensemble. Aggregated ratio.", Icon: Film },
  { code: "06", name: "Audio Spectrogram", desc: "Spectral features detect synthetic-voice frequency artifacts.", Icon: AudioLines },
  { code: "07", name: "Text LLM", desc: "Classifies AI authorship from stylistic and structural cues.", Icon: Type },
];

const NUMBERS = [
  { v: "07", l: "Independent analyzers" },
  { v: "≈4s", l: "Median image verdict" },
  { v: "500MB", l: "Max upload" },
  { v: "JWT", l: "End-to-end auth" },
];

const PRINCIPLES = [
  { kw: "Forensic", body: "We treat every submission like an evidence file. Crop marks. Case IDs. Provenance trails.", accent: "violet" },
  { kw: "Transparent", body: "No black-box scores. Each analyzer publishes raw JSON evidence beside its verdict.", accent: "cyan" },
  { kw: "Skeptical", body: "If two methods disagree, we surface that. Inconclusive is a valid answer.", accent: "amber" },
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
                ProofLayer is a forensic verification lab for synthetic media.
                Seven independent analyzers cross-examine every file -
                and publish their evidence, not just their verdicts.
              </motion.p>

              <motion.div
                variants={fadeUp}
                transition={{ duration: 0.6 }}
                className="mt-10 flex flex-wrap items-center gap-3"
              >
                <MagneticBtn to={authedCta} className="btn-forensic group text-sm">
                  <span>{user ? "Submit Evidence" : "Submit Evidence"}</span>
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
                      <CountUp value={82} />
                    </div>
                    <div className="font-display text-3xl text-ink-500 mb-3">%</div>
                  </div>

                  <div className="space-y-2.5 mb-5">
                    {[
                      { l: "AI-3 ENSEMBLE", v: "fake", c: "text-signal-blood", n: "0.91" },
                      { l: "ELA", v: "suspicious", c: "text-signal-amber", n: "0.62" },
                      { l: "VLM", v: "fake", c: "text-signal-blood", n: "0.88" },
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
                    <span>Aggregated · weighted</span>
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

        {/* PIPELINE */}
        <section className="pb-28">
          <motion.div
            className="flex items-end justify-between mb-14 flex-wrap gap-6"
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <div>
              <div className="label-mono mb-3 flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-signal-cyan rounded-full pulse-dot" />
                The Pipeline
              </div>
              <h2 className="font-display text-6xl lg:text-7xl text-ink-50 leading-[0.95]">
                Seven witnesses<span className="italic text-iris">,</span>
                <br />
                one verdict.
              </h2>
            </div>
            <p className="max-w-md text-ink-200 leading-relaxed">
              Each analyzer operates independently. We aggregate by weighted confidence -
              never by majority vote. Disagreement is escalated, not silenced.
            </p>
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
                  className="grid grid-cols-12 gap-6 py-7 cursor-default group"
                >
                  <div className="col-span-1 font-mono text-xs text-ink-500 ticker pt-1">
                    {String(i + 1).padStart(2, "0")}
                  </div>
                  <motion.div
                    className="col-span-1 text-signal-amber/70 flex items-start pt-1"
                    variants={{ hover: { color: "var(--signal-amber)", scale: 1.15 } }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
                    <Icon size={22} strokeWidth={1.5} />
                  </motion.div>
                  <motion.div
                    className="col-span-4 font-display text-2xl lg:text-3xl text-ink-50 leading-tight"
                    variants={{ hover: { x: 6 } }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
                    {a.name}
                  </motion.div>
                  <p className="col-span-6 text-sm text-ink-300 leading-relaxed">{a.desc}</p>
                </motion.div>
              );
            })}
            <motion.div
              variants={fadeUp}
              transition={{ duration: 0.6 }}
              className="grid grid-cols-12 gap-6 py-7"
            >
              <div className="col-span-1" />
              <div className="col-span-1 text-signal-violet/70 flex items-start pt-1">
                <Sparkles size={22} strokeWidth={1.5} />
              </div>
              <div className="col-span-4 font-display text-2xl lg:text-3xl italic text-ink-300 leading-tight">
                More to come.
              </div>
              <div className="col-span-6 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500 pt-2">
                C2PA · audio deepfake · OCR
              </div>
            </motion.div>
          </motion.div>
        </section>

        {/* WIDGET */}
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
              One script tag. Real-time verdict, fed by your submission's SHA-256.
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
<span className="text-signal-violet">{"<script"}</span> <span className="text-signal-cyan">src</span>=<span className="text-signal-amber">"https://prooflayer.app/widget.js"</span><span className="text-signal-violet">{"></script>"}</span>{"\n"}
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
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10 flex flex-wrap items-center justify-between gap-4 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">
          <span>© ProofLayer Lab - {new Date().getFullYear()}</span>
          <div className="flex gap-6">
            <a href="https://api.prooflayer.cloud/api/docs/" className="hover:text-signal-amber transition-colors">API</a>
            <a href="https://github.com/jeezdredd/prooflayer" className="hover:text-signal-amber transition-colors">Source</a>
            <span className="text-iris">Confidence ≠ Certainty</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
