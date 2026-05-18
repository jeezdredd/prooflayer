import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { auth } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";
import ShaderBackground from "../components/ui/ShaderBackground";

type Status = "pending" | "ok" | "fail";

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [status, setStatus] = useState<Status>("pending");
  const [message, setMessage] = useState("");
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  useEffect(() => {
    if (!token) {
      setStatus("fail");
      setMessage("Missing verification token.");
      return;
    }
    auth
      .verifyEmail(token)
      .then(async (res) => {
        setStatus("ok");
        setMessage(res.data.detail);
        try {
          const me = await auth.me();
          setUser(me.data);
        } catch {
          if (user) setUser({ ...user, is_verified: true });
        }
      })
      .catch((err) => {
        setStatus("fail");
        setMessage(err?.response?.data?.detail || "Verification failed.");
      });
  }, [token, setUser, user]);

  return (
    <div className="min-h-screen flex items-center justify-center text-ink-100 relative overflow-hidden px-6">
      <ShaderBackground variant="noir" />
      <motion.div
        className="w-full max-w-md relative z-10 case-card p-10 text-center"
        initial={{ opacity: 0, y: 20, filter: "blur(8px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0)" }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        <Link to="/" className="block mb-8 font-display text-3xl text-white">
          ProofLayer
        </Link>
        {status === "pending" && (
          <div className="flex flex-col items-center gap-3 text-ink-300">
            <Loader2 className="w-10 h-10 animate-spin" />
            <p>Verifying your email...</p>
          </div>
        )}
        {status === "ok" && (
          <div className="flex flex-col items-center gap-4">
            <CheckCircle2 className="w-12 h-12 text-sage-400" />
            <h1 className="font-display text-2xl text-white">Email verified</h1>
            <p className="text-sm text-ink-400">{message}</p>
            <Link
              to="/upload"
              className="mt-4 inline-block bg-white text-black px-6 py-2.5 text-sm font-medium hover:bg-ink-200 transition"
            >
              Continue to ProofLayer
            </Link>
          </div>
        )}
        {status === "fail" && (
          <div className="flex flex-col items-center gap-4">
            <XCircle className="w-12 h-12 text-blood-500" />
            <h1 className="font-display text-2xl text-white">Could not verify</h1>
            <p className="text-sm text-ink-400">{message}</p>
            <Link
              to="/login"
              className="mt-4 inline-block border border-ink-700 text-ink-200 px-6 py-2.5 text-sm font-medium hover:bg-ink-800 transition"
            >
              Back to login
            </Link>
          </div>
        )}
      </motion.div>
    </div>
  );
}
