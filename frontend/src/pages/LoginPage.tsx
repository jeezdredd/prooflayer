import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { useLogin } from "../hooks/useAuth";
import ShaderBackground from "../components/ui/ShaderBackground";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    login.mutate({ email, password });
  };

  return (
    <div className="min-h-screen flex items-center justify-center text-ink-100 relative overflow-hidden px-6">
      <ShaderBackground variant="noir" />
      <div className="absolute inset-0 -z-10 bg-grid-fine bg-grid-fine opacity-[0.4] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,black,transparent)]" />

      <motion.div
        className="w-full max-w-md relative z-10"
        initial={{ opacity: 0, y: 20, filter: "blur(8px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0)" }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      >
        <Link to="/" className="block mb-10 text-center">
          <motion.span
            className="font-display text-5xl text-white tracking-tight inline-block drop-shadow-[0_2px_24px_rgba(0,0,0,0.6)]"
            whileHover={{ scale: 1.04 }}
            transition={{ type: "spring", stiffness: 300 }}
          >
            Proof<span className="italic text-iris">Layer</span>
          </motion.span>
        </Link>

        <form onSubmit={handleSubmit} className="case-card crop-marks">
          <div className="flex items-center justify-between px-6 py-3 border-b border-[var(--line)]">
            <div className="flex items-center gap-3">
              <span className="relative inline-flex">
                <span className="w-1.5 h-1.5 rounded-full bg-signal-amber" />
                <motion.span
                  className="absolute inset-0 rounded-full bg-signal-amber"
                  animate={{ scale: [1, 2.4], opacity: [0.7, 0] }}
                  transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
                />
              </span>
              <span className="label-mono">Authentication</span>
            </div>
            <span className="font-mono text-[10px] text-ink-500">SECURE</span>
          </div>

          <motion.div
            className="p-6 space-y-5"
            initial="hidden"
            animate="visible"
            variants={{ visible: { transition: { staggerChildren: 0.08, delayChildren: 0.15 } } }}
          >
            <motion.div variants={{ hidden: { opacity: 0, y: 8 }, visible: { opacity: 1, y: 0 } }}>
              <label className="label-mono block mb-2">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                className="input-forensic"
                placeholder="agent@prooflayer.cloud"
              />
            </motion.div>
            <motion.div variants={{ hidden: { opacity: 0, y: 8 }, visible: { opacity: 1, y: 0 } }}>
              <label className="label-mono block mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="input-forensic"
                placeholder="••••••••••"
              />
            </motion.div>

            {login.isError && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: [0, -8, 8, -8, 8, 0] }}
                transition={{ duration: 0.5 }}
                className="flex items-center gap-2 p-3 border border-signal-blood bg-signal-blood/5"
              >
                <span className="w-4 h-4 border border-signal-blood text-signal-blood text-[10px] font-bold flex items-center justify-center">!</span>
                <span className="font-mono text-[11px] text-signal-blood">Invalid credentials. Access denied.</span>
              </motion.div>
            )}

            <motion.button
              variants={{ hidden: { opacity: 0, y: 8 }, visible: { opacity: 1, y: 0 } }}
              type="submit"
              disabled={login.isPending}
              className="btn-forensic w-full justify-center"
              whileTap={{ scale: 0.98 }}
            >
              {login.isPending ? "Authenticating…" : "Authenticate →"}
            </motion.button>
          </motion.div>

          <div className="dot-divider mx-6" />
          <div className="px-6 py-4 text-center font-mono text-[11px] text-ink-500">
            No clearance?{" "}
            <Link to="/register" className="text-signal-amber hover:underline">
              Request access →
            </Link>
          </div>
        </form>

        <div className="mt-6 text-center font-mono text-[10px] uppercase tracking-[0.16em] text-white/60">
          ProofLayer Lab · Forensic Verification
        </div>
      </motion.div>
    </div>
  );
}
