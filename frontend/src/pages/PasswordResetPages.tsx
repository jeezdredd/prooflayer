import { useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import { CheckCircle2, MailCheck } from "lucide-react";
import { auth } from "../api/endpoints";
import ShaderBackground from "../components/ui/ShaderBackground";
import LangSwitch from "../components/LangSwitch";
import { t } from "../i18n";

function AuthShell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center text-ink-100 relative overflow-hidden px-6 py-16">
      <ShaderBackground variant="noir" />
      <LangSwitch className="absolute top-4 right-4 z-20" />
      <motion.div
        className="w-full max-w-md relative z-10"
        initial={{ opacity: 0, y: 20, filter: "blur(8px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0)" }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      >
        <Link to="/" className="block mb-10 text-center">
          <span className="font-display text-5xl text-white tracking-tight">
            Proof<span className="italic text-iris">Layer</span>
          </span>
        </Link>
        <div className="case-card">
          <div className="flex items-center gap-3 px-7 py-4 border-b border-[var(--line)]">
            <span className="w-1.5 h-1.5 rounded-full bg-signal-amber" />
            <span className="label-mono">{label}</span>
          </div>
          <div className="p-7 space-y-6">{children}</div>
        </div>
      </motion.div>
    </div>
  );
}

function ErrorLine({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-signal-blood/40 bg-signal-blood/5 px-4 py-3 font-mono text-[11px] text-signal-blood">{text}</div>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await auth.requestPasswordReset(email);
      setSent(true);
    } catch {
      setError(t("Too many attempts. Try again in an hour."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell label={t("Password reset")}>
      {sent ? (
        <div className="flex flex-col items-center text-center gap-4 py-2">
          <MailCheck className="w-11 h-11 text-signal-sage" strokeWidth={1.5} />
          <h1 className="font-display text-3xl text-ink-50">{t("Check your inbox")}</h1>
          <p className="text-sm text-ink-300 leading-relaxed">
            {t("If {email} has an account, a link to set a new password is on its way. It works for one hour.", { email })}
          </p>
          <Link to="/login" className="btn-ghost mt-2">{t("Back to sign in")}</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-6">
          <div>
            <h1 className="font-display text-3xl text-ink-50 leading-tight">{t("Forgot your password?")}</h1>
            <p className="text-sm text-ink-400 mt-2 leading-relaxed">{t("Enter the email you signed up with and we will send you a link to set a new one.")}</p>
          </div>
          <div>
            <label className="label-mono block mb-2">{t("Email Address")}</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus className="input-forensic" placeholder="agent@prooflayer.cloud" />
          </div>
          {error && <ErrorLine text={error} />}
          <button type="submit" disabled={busy} className="btn-forensic w-full justify-center">
            {busy ? t("Sending…") : `${t("Send reset link")} →`}
          </button>
          <div className="text-center font-mono text-[11px] text-ink-500">
            <Link to="/login" className="text-signal-amber hover:underline">{t("Back to sign in")}</Link>
          </div>
        </form>
      )}
    </AuthShell>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const uid = params.get("uid") || "";
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setError(t("Passwords do not match."));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await auth.confirmPasswordReset(uid, token, password);
      setDone(true);
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { detail?: string; password?: string[] } } })?.response?.data;
      setError(data?.password?.length ? data.password.map((m) => t(m)).join(" ") : t(data?.detail || "This reset link is invalid or has expired."));
    } finally {
      setBusy(false);
    }
  };

  if (!uid || !token) {
    return (
      <AuthShell label={t("Password reset")}>
        <ErrorLine text={t("This reset link is invalid or has expired.")} />
        <Link to="/forgot-password" className="btn-forensic w-full justify-center">{t("Request a new link")} →</Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell label={t("Password reset")}>
      {done ? (
        <div className="flex flex-col items-center text-center gap-4 py-2">
          <CheckCircle2 className="w-11 h-11 text-signal-sage" strokeWidth={1.5} />
          <h1 className="font-display text-3xl text-ink-50">{t("Password changed")}</h1>
          <p className="text-sm text-ink-300 leading-relaxed">{t("You were signed out everywhere. Sign in with your new password.")}</p>
          <Link to="/login" className="btn-forensic mt-2">{t("Sign in")} →</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-6">
          <div>
            <h1 className="font-display text-3xl text-ink-50 leading-tight">{t("Set a new password")}</h1>
            <p className="text-sm text-ink-400 mt-2 leading-relaxed">{t("At least 8 characters, not only digits, not too common.")}</p>
          </div>
          <div>
            <label className="label-mono block mb-2">{t("New password")}</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoFocus className="input-forensic" autoComplete="new-password" />
          </div>
          <div>
            <label className="label-mono block mb-2">{t("Repeat the password")}</label>
            <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required className="input-forensic" autoComplete="new-password" />
          </div>
          {error && <ErrorLine text={error} />}
          <button type="submit" disabled={busy} className="btn-forensic w-full justify-center">
            {busy ? t("Saving…") : `${t("Save new password")} →`}
          </button>
        </form>
      )}
    </AuthShell>
  );
}

export function UnsubscribePage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [state, setState] = useState<"idle" | "busy" | "done" | "fail">("idle");

  const confirm = async () => {
    setState("busy");
    try {
      await auth.unsubscribe(token);
      setState("done");
    } catch {
      setState("fail");
    }
  };

  return (
    <AuthShell label={t("Product updates")}>
      {state === "done" ? (
        <div className="flex flex-col items-center text-center gap-4 py-2">
          <CheckCircle2 className="w-11 h-11 text-signal-sage" strokeWidth={1.5} />
          <h1 className="font-display text-3xl text-ink-50">{t("You are unsubscribed")}</h1>
          <p className="text-sm text-ink-300 leading-relaxed">{t("No more product updates. Account and security emails still arrive. You can turn updates back on in your account.")}</p>
          <Link to="/" className="btn-ghost mt-2">{t("Go to ProofLayer")}</Link>
        </div>
      ) : (
        <div className="space-y-6">
          <div>
            <h1 className="font-display text-3xl text-ink-50 leading-tight">{t("Stop product updates?")}</h1>
            <p className="text-sm text-ink-400 mt-2 leading-relaxed">{t("You will no longer get emails about new features. Account and security emails still arrive.")}</p>
          </div>
          {(state === "fail" || !token) && <ErrorLine text={t("This unsubscribe link is invalid.")} />}
          <button type="button" onClick={confirm} disabled={!token || state === "busy"} className="btn-forensic w-full justify-center">
            {state === "busy" ? t("Saving…") : `${t("Unsubscribe")} →`}
          </button>
        </div>
      )}
    </AuthShell>
  );
}
