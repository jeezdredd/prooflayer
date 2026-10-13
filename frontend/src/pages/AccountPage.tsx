import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { auth } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";
import { toast } from "../components/ui/Toast";

const LABEL = "font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500";

function errorDetail(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback;
}

export default function AccountPage() {
  const { user, setUser, logout } = useAuthStore();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [forgetTraining, setForgetTraining] = useState(false);
  const [confirmText, setConfirmText] = useState("");

  const consent = useMutation({
    mutationFn: (allow: boolean) => auth.updateMe({ allow_training: allow }).then((r) => r.data),
    onSuccess: (data) => {
      setUser(data);
      toast.success(data.allow_training ? "Thank you, consent recorded" : "Consent withdrawn; your training copies were deleted");
    },
    onError: () => toast.error("Could not save"),
  });

  const remove = useMutation({
    mutationFn: () => auth.deleteMe(password, forgetTraining),
    onSuccess: () => {
      logout();
      navigate("/");
      toast.success("Your account and uploads were deleted");
    },
    onError: (err) => toast.error(errorDetail(err, "Could not delete the account")),
  });

  if (!user) return null;

  return (
    <div className="max-w-2xl">
      <span className="label-mono">Account</span>
      <h1 className="font-display text-4xl text-ink-50 mt-2 mb-8">{user.username}</h1>

      <section className="border-t border-[var(--line-strong)] py-6">
        <div className={LABEL}>Signed in as</div>
        <div className="text-ink-100 mt-1">{user.email}</div>
      </section>

      <section className="border-t border-[var(--line-strong)] py-6">
        <div className={LABEL}>Help improve detection</div>
        <label className="mt-3 flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={!!user.allow_training}
            disabled={consent.isPending}
            onChange={(e) => consent.mutate(e.target.checked)}
            className="mt-1 accent-amber-400"
          />
          <span className="text-sm text-ink-300 leading-relaxed">
            Allow ProofLayer to keep a copy of my personal uploads that our reviewers label as real or AI, and use it
            to train its detectors. Copies are stored without my account details. Class work is never used. I can
            withdraw at any time, and my copies are deleted when I do.
          </span>
        </label>
        {user.training_consent_at && (
          <div className="font-mono text-[11px] text-ink-500 mt-2">Consent given {new Date(user.training_consent_at).toLocaleDateString()}</div>
        )}
      </section>

      <section className="border-t border-[var(--line-strong)] py-6">
        <div className={LABEL}>Your data</div>
        <p className="text-sm text-ink-400 mt-2 leading-relaxed">
          Personal uploads are deleted from storage 90 days after upload; verdicts stay in your history. To get a copy
          of your data or correct it, write to <a href="mailto:legal@prooflayer.cloud" className="underline hover:text-ink-100">legal@prooflayer.cloud</a>.
          See the <Link to="/privacy" className="underline hover:text-ink-100">Privacy Policy</Link>.
        </p>
      </section>

      <section className="border-t border-signal-blood/40 py-6">
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-signal-blood">Delete account</div>
        <p className="text-sm text-ink-400 mt-2 leading-relaxed">
          Deletes your account, every upload and its results, your API keys and your class memberships, including work
          you handed in to classes. This cannot be undone. If you own a school, delete the school first.
        </p>
        <form
          className="mt-4 space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (confirmText === "DELETE" && password) remove.mutate();
          }}
        >
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Your password"
            autoComplete="current-password"
            className="w-full bg-transparent border border-[var(--line-strong)] px-3 py-2 text-ink-50 focus:border-signal-blood outline-none"
          />
          <input
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="Type DELETE to confirm"
            className="w-full bg-transparent border border-[var(--line-strong)] px-3 py-2 font-mono text-ink-50 focus:border-signal-blood outline-none"
          />
          {user.allow_training && (
            <label className="flex items-start gap-3 text-sm text-ink-300 cursor-pointer">
              <input type="checkbox" checked={forgetTraining} onChange={(e) => setForgetTraining(e.target.checked)} className="mt-1" />
              Also delete the anonymous training copies of my uploads
            </label>
          )}
          <button
            type="submit"
            disabled={confirmText !== "DELETE" || !password || remove.isPending}
            className="border border-signal-blood/60 text-signal-blood px-4 py-2 font-mono text-[11px] uppercase tracking-[0.14em] hover:bg-signal-blood/10 disabled:opacity-40"
          >
            {remove.isPending ? "Deleting…" : "Delete my account"}
          </button>
        </form>
      </section>
    </div>
  );
}
