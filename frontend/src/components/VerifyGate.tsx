import { useState } from "react";
import { Link } from "react-router-dom";
import { MailWarning, RefreshCw, LayoutDashboard } from "lucide-react";
import { motion } from "motion/react";
import { auth } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";

type State = "idle" | "sending" | "sent" | "error";

export default function VerifyGate() {
  const user = useAuthStore((s) => s.user);
  const [state, setState] = useState<State>("idle");

  const resend = async () => {
    setState("sending");
    try {
      await auth.resendVerification();
      setState("sent");
    } catch {
      setState("error");
    }
  };

  return (
    <motion.div
      className="case-card crop-marks p-10 max-w-xl mx-auto text-center"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="flex justify-center mb-5">
        <div className="w-14 h-14 border border-signal-amber/50 bg-signal-amber/10 flex items-center justify-center rounded-sm">
          <MailWarning className="w-7 h-7 text-signal-amber" />
        </div>
      </div>
      <span className="label-mono">Verification Required</span>
      <h1 className="font-display text-3xl text-white mt-3">
        Verify your email to continue
      </h1>
      <p className="text-sm text-ink-400 mt-3">
        This feature is locked until <span className="font-mono text-ink-200">{user?.email}</span> is verified.
        Open the link we sent to your inbox, or request a fresh one.
      </p>
      <div className="mt-7 flex items-center justify-center gap-3 flex-wrap">
        <button
          onClick={resend}
          disabled={state === "sending" || state === "sent"}
          className="inline-flex items-center gap-2 border border-signal-amber/60 text-signal-amber px-5 py-2.5 text-xs font-mono uppercase tracking-[0.14em] hover:bg-signal-amber/10 transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${state === "sending" ? "animate-spin" : ""}`} />
          {state === "sent" ? "email sent" : state === "error" ? "retry" : "resend email"}
        </button>
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-2 border border-ink-700 text-ink-300 px-5 py-2.5 text-xs font-mono uppercase tracking-[0.14em] hover:bg-ink-800 hover:text-ink-100 transition"
        >
          <LayoutDashboard className="w-3.5 h-3.5" />
          back to dashboard
        </Link>
      </div>
      {state === "error" && (
        <p className="mt-4 text-xs text-signal-blood font-mono">Failed to send. Try again.</p>
      )}
    </motion.div>
  );
}
