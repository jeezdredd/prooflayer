import { useState } from "react";
import { MailWarning, RefreshCw } from "lucide-react";
import { auth } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";

export default function EmailVerifyBanner() {
  const user = useAuthStore((s) => s.user);
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");

  if (!user || user.is_verified) return null;

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
    <div className="mb-6 flex items-center gap-3 border border-amber-500/40 bg-amber-500/10 px-4 py-2.5 text-xs">
      <MailWarning className="w-4 h-4 text-amber-400 shrink-0" />
      <div className="flex-1 text-amber-100">
        Verify <span className="font-mono">{user.email}</span> to unlock full features. Check your inbox for the link.
      </div>
      <button
        onClick={resend}
        disabled={state === "sending" || state === "sent"}
        className="flex items-center gap-1.5 border border-amber-400/50 px-3 py-1 text-amber-200 hover:bg-amber-500/20 transition disabled:opacity-50"
      >
        <RefreshCw className={`w-3 h-3 ${state === "sending" ? "animate-spin" : ""}`} />
        {state === "sent" ? "sent" : state === "error" ? "retry" : "resend"}
      </button>
    </div>
  );
}
