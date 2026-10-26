import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { auth } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";
import { toast } from "../components/ui/Toast";
import { AGE_HINT, AGE_LABEL, legalHref } from "../legal";
import { IS_CLASSROOM_APP } from "../appMode";
import { locale, msg, t } from "../i18n";
import type { User } from "../types";

const LABEL = "font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500";
const FIELD = "w-full bg-transparent border border-[var(--line-strong)] px-3 py-2 text-ink-50 focus:border-signal-amber outline-none";
const MAIN_BUTTON = "border border-signal-amber/60 text-signal-amber px-4 py-2 font-mono text-[11px] uppercase tracking-[0.14em] hover:bg-signal-amber/10 disabled:opacity-40";
const QUIET_BUTTON = "border border-[var(--line-strong)] text-ink-300 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.14em] hover:text-ink-100 disabled:opacity-40";
const TOO_MANY = msg("Too many tries. Wait an hour and try again.");
const SEND_FAILED = msg("Could not send the link. Try again later.");

const CHANGE_ERRORS: Record<string, string> = {
  wrong_password: msg("The password is not right."),
  email_taken: msg("Another account already uses this address."),
  same_email: msg("This is already your address."),
  invalid_email: msg("Enter a full email address, like name@example.com."),
};

interface ErrorResponse {
  status?: number;
  data?: { detail?: string; code?: string };
}

function errorResponse(err: unknown): ErrorResponse {
  return (err as { response?: ErrorResponse })?.response ?? {};
}

function errorDetail(err: unknown, fallback: string): string {
  const detail = errorResponse(err).data?.detail;
  return detail ? t(detail) : fallback;
}

function changeError(err: unknown): string {
  const { status, data } = errorResponse(err);
  if (status === 429) return t(TOO_MANY);
  if (data?.code && CHANGE_ERRORS[data.code]) return t(CHANGE_ERRORS[data.code]);
  return data?.detail ? t(data.detail) : t(SEND_FAILED);
}

function patchUser(patch: Partial<User>) {
  const { user, setUser } = useAuthStore.getState();
  if (user) setUser({ ...user, ...patch });
}

function EmailSection({ user }: { user: User }) {
  const setUser = useAuthStore((s) => s.setUser);
  const [open, setOpen] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const pending = user.pending_email ?? null;

  useEffect(() => {
    if (!pending) return;
    const refresh = () => {
      auth.me().then((r) => setUser(r.data)).catch(() => undefined);
    };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [pending, setUser]);

  const close = () => {
    setOpen(false);
    setNewEmail("");
    setPassword("");
    setError("");
  };

  const request = useMutation({
    mutationFn: () => auth.requestEmailChange(newEmail.trim(), password).then((r) => r.data),
    onSuccess: (data) => {
      patchUser({ pending_email: data.pending_email });
      close();
    },
    onError: (err) => setError(changeError(err)),
  });

  const resend = useMutation({
    mutationFn: () => auth.resendEmailChange().then((r) => r.data),
    onSuccess: (data) => toast.success(t("We sent the link again to {email}", { email: data.pending_email ?? "" })),
    onError: (err) => {
      const { status } = errorResponse(err);
      if (status === 404) {
        patchUser({ pending_email: null });
        toast.error(t("This change has expired. Start again."));
        return;
      }
      toast.error(status === 429 ? t(TOO_MANY) : errorDetail(err, t(SEND_FAILED)));
    },
  });

  const cancel = useMutation({
    mutationFn: () => auth.cancelEmailChange(),
    onSuccess: () => {
      patchUser({ pending_email: null });
      toast.success(t("Email change cancelled"));
    },
    onError: () => toast.error(t("Could not save")),
  });

  return (
    <section className="border-t border-[var(--line-strong)] py-6">
      <div className={LABEL}>{t("Email")}</div>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-ink-100 break-all">{user.email}</span>
        {user.is_verified ? (
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-signal-sage">{t("confirmed")}</span>
        ) : (
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-signal-amber">{t("not confirmed")}</span>
        )}
      </div>
      {!user.is_verified && (
        <p className="text-xs text-ink-500 mt-2">{t("Open the link we sent to this address to confirm it.")}</p>
      )}
      {user.is_demo ? (
        <p className="text-sm text-ink-400 mt-3">{t("This is a shared demo account, so its email cannot be changed.")}</p>
      ) : pending ? (
        <div className="mt-4 border border-signal-amber/40 p-4">
          <p className="text-sm text-ink-200 leading-relaxed break-words">
            {t("We sent a link to {email}. Your address changes when you open it.", { email: pending })}
          </p>
          <p className="text-xs text-ink-500 mt-1 break-words">
            {t("Until then, sign in with {email}. The link works for 24 hours.", { email: user.email })}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={() => resend.mutate()} disabled={resend.isPending} className={MAIN_BUTTON}>
              {resend.isPending ? t("Sending…") : t("Send again")}
            </button>
            <button type="button" onClick={() => cancel.mutate()} disabled={cancel.isPending} className={QUIET_BUTTON}>
              {t("Cancel the change")}
            </button>
          </div>
        </div>
      ) : open ? (
        <form
          className="mt-4 space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (newEmail.trim() && password && !request.isPending) request.mutate();
          }}
        >
          <p className="text-xs text-ink-500 leading-relaxed">
            {t("We will send a link to the new address. Your email changes only after you open it.")}
          </p>
          <input
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder={t("New email")}
            aria-label={t("New email")}
            autoComplete="email"
            className={FIELD}
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t("Your current password")}
            aria-label={t("Your current password")}
            autoComplete="current-password"
            className={FIELD}
          />
          {error && <p role="alert" className="text-sm text-signal-blood">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={!newEmail.trim() || !password || request.isPending} className={MAIN_BUTTON}>
              {request.isPending ? t("Sending…") : t("Send link")}
            </button>
            <button type="button" onClick={close} className={QUIET_BUTTON}>
              {t("Cancel")}
            </button>
          </div>
        </form>
      ) : (
        <button type="button" onClick={() => setOpen(true)} className={`${QUIET_BUTTON} mt-4`}>
          {t("Change email")}
        </button>
      )}
    </section>
  );
}

export default function AccountPage() {
  const { user, setUser, logout } = useAuthStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const [forgetTraining, setForgetTraining] = useState(false);
  const [confirmText, setConfirmText] = useState("");

  const consent = useMutation({
    mutationFn: (allow: boolean) => auth.updateMe({ allow_training: allow }).then((r) => r.data),
    onSuccess: (data) => {
      setUser(data);
      toast.success(data.allow_training ? t("Thank you, consent recorded") : t("Consent withdrawn; your training copies were deleted"));
    },
    onError: () => toast.error(t("Could not save")),
  });

  const updates = useMutation({
    mutationFn: (on: boolean) => auth.updateMe({ email_updates: on }).then((r) => r.data),
    onSuccess: (data) => {
      setUser(data);
      toast.success(data.email_updates ? t("Product updates are on") : t("Product updates are off"));
    },
    onError: () => toast.error(t("Could not save")),
  });

  const age = useMutation({
    mutationFn: (isAdult: boolean) => auth.updateMe({ is_adult: isAdult }).then((r) => r.data),
    onSuccess: (data) => {
      setUser(data);
      queryClient.setQueryData(["me", data.id], data);
      queryClient.invalidateQueries({ queryKey: ["feed"] });
      queryClient.invalidateQueries({ queryKey: ["feed-detail"] });
      toast.success(data.is_adult ? t("Saved: you are 18 or older") : t("Saved: public uploads from others are hidden"));
    },
    onError: () => toast.error(t("Could not save")),
  });

  const remove = useMutation({
    mutationFn: () => auth.deleteMe(password, forgetTraining),
    onSuccess: () => {
      logout();
      navigate("/");
      toast.success(t("Your account and uploads were deleted"));
    },
    onError: (err) => toast.error(errorDetail(err, t("Could not delete the account"))),
  });

  if (!user) return null;

  return (
    <div className="max-w-2xl">
      <span className="label-mono">{t("Account")}</span>
      <h1 className="font-display text-4xl text-ink-50 mt-2 mb-8">{user.username}</h1>

      <EmailSection user={user} />

      <section className="border-t border-[var(--line-strong)] py-6">
        <div className={LABEL}>{t("Age")}</div>
        <label className="mt-3 flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={!!user.is_adult}
            disabled={age.isPending}
            onChange={(e) => age.mutate(e.target.checked)}
            className="mt-1 accent-amber-400"
          />
          <span className="text-sm text-ink-300 leading-relaxed">
            {t(AGE_LABEL)}
            <span className="block text-xs text-ink-500 mt-1">{t(AGE_HINT)}</span>
          </span>
        </label>
      </section>

      <section className="border-t border-[var(--line-strong)] py-6">
        <div className={LABEL}>{t("Help improve detection")}</div>
        <label className="mt-3 flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={!!user.allow_training}
            disabled={consent.isPending}
            onChange={(e) => consent.mutate(e.target.checked)}
            className="mt-1 accent-amber-400"
          />
          <span className="text-sm text-ink-300 leading-relaxed">
            {t("Allow ProofLayer to keep a copy of my personal uploads that our reviewers label as real or AI, and use it to train its detectors. Copies are stored without my account details. Class work is never used. I can withdraw at any time, and my copies are deleted when I do.")}
          </span>
        </label>
        {user.training_consent_at && (
          <div className="font-mono text-[11px] text-ink-500 mt-2">{t("Consent given {date}", { date: new Date(user.training_consent_at).toLocaleDateString(locale()) })}</div>
        )}
      </section>

      <section className="border-t border-[var(--line-strong)] py-6">
        <div className={LABEL}>{t("Emails")}</div>
        <label className="mt-3 flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={user.email_updates !== false}
            disabled={updates.isPending}
            onChange={(e) => updates.mutate(e.target.checked)}
            className="mt-1 accent-amber-400"
          />
          <span className="text-sm text-ink-300 leading-relaxed">
            {t("Send me product updates: new detectors, features and changes to ProofLayer, a few times a month at most. Account and security emails always arrive.")}
          </span>
        </label>
        <p className="font-mono text-[11px] text-ink-500 mt-3">{t("Emails come in the language you use on the site.")}</p>
      </section>

      <section className="border-t border-[var(--line-strong)] py-6">
        <div className={LABEL}>{t("Your data")}</div>
        <p className="text-sm text-ink-400 mt-2 leading-relaxed">
          {t("Personal uploads are deleted from storage 90 days after upload; verdicts stay in your history. To get a copy of your data or correct it, write to")}{" "}
          <a href="mailto:legal@prooflayer.cloud" className="underline hover:text-ink-100">legal@prooflayer.cloud</a>.{" "}
          {t("See the")}{" "}
          {IS_CLASSROOM_APP ? (
            <a href={legalHref("/privacy")} className="underline hover:text-ink-100">{t("Privacy Policy")}</a>
          ) : (
            <Link to="/privacy" className="underline hover:text-ink-100">{t("Privacy Policy")}</Link>
          )}
          .
        </p>
      </section>

      <section className="border-t border-signal-blood/40 py-6">
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-signal-blood">{t("Delete account")}</div>
        <p className="text-sm text-ink-400 mt-2 leading-relaxed">
          {t("Deletes your account, every upload and its results, your API keys and your class memberships, including work you handed in to classes. This cannot be undone. If you own a school, delete the school first.")}
        </p>
        {user.is_demo ? (
          <p className="text-sm text-ink-400 mt-3">{t("This is a shared demo account, so it cannot be deleted.")}</p>
        ) : (
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
              placeholder={t("Your password")}
              autoComplete="current-password"
              className="w-full bg-transparent border border-[var(--line-strong)] px-3 py-2 text-ink-50 focus:border-signal-blood outline-none"
            />
            <input
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder={t("Type DELETE to confirm")}
              className="w-full bg-transparent border border-[var(--line-strong)] px-3 py-2 font-mono text-ink-50 focus:border-signal-blood outline-none"
            />
            {user.allow_training && (
              <label className="flex items-start gap-3 text-sm text-ink-300 cursor-pointer">
                <input type="checkbox" checked={forgetTraining} onChange={(e) => setForgetTraining(e.target.checked)} className="mt-1" />
                {t("Also delete the anonymous training copies of my uploads")}
              </label>
            )}
            <button
              type="submit"
              disabled={confirmText !== "DELETE" || !password || remove.isPending}
              className="border border-signal-blood/60 text-signal-blood px-4 py-2 font-mono text-[11px] uppercase tracking-[0.14em] hover:bg-signal-blood/10 disabled:opacity-40"
            >
              {remove.isPending ? t("Deleting…") : t("Delete my account")}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
