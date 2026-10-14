import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { auth } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";
import { AGE_HINT, AGE_LABEL, legalHref } from "../legal";
import { t } from "../i18n";

const LINK = "text-signal-amber hover:underline";

function errorDetail(err: unknown): string {
  const data = (err as { response?: { data?: Record<string, unknown> } })?.response?.data;
  if (data && typeof data.detail === "string") return t(data.detail);
  const first = data ? Object.values(data)[0] : null;
  if (Array.isArray(first) && first.length) return t(String(first[0]));
  return t("Could not save. Please try again.");
}

function TermsPanel({ initialAdult }: { initialAdult: boolean }) {
  const { setUser, logout } = useAuthStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [accepted, setAccepted] = useState(false);
  const [isAdult, setIsAdult] = useState(initialAdult);

  const accept = useMutation({
    mutationFn: () => auth.acceptTerms(isAdult).then((r) => r.data),
    onSuccess: (user) => {
      setUser(user);
      queryClient.setQueryData(["me", user.id], user);
      queryClient.invalidateQueries({ queryKey: ["feed"] });
      queryClient.invalidateQueries({ queryKey: ["feed-detail"] });
    },
  });

  const signOut = async () => {
    await auth.logout().catch(() => null);
    logout();
    navigate("/login");
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-ink-950/90 backdrop-blur-sm px-4">
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="terms-gate-title"
        className="w-full max-w-md bg-ink-950 border border-[var(--line-strong)] p-6"
        onSubmit={(e) => {
          e.preventDefault();
          if (accepted && !accept.isPending) accept.mutate();
        }}
      >
        <h2 id="terms-gate-title" className="font-display text-2xl text-ink-50 leading-tight">
          {t("We updated our Terms and Privacy Notice")}
        </h2>
        <p className="text-sm text-ink-400 mt-3 leading-relaxed">
          {t("Please read the")}{" "}
          <a href={legalHref("/terms")} target="_blank" rel="noopener noreferrer" className={LINK}>{t("Terms of Service")}</a>,{" "}
          <a href={legalHref("/privacy")} target="_blank" rel="noopener noreferrer" className={LINK}>{t("Privacy Notice")}</a> {t("and the")}{" "}
          <a href={legalHref("/data-processing")} target="_blank" rel="noopener noreferrer" className={LINK}>{t("Data Processing terms")}</a>.
        </p>
        <div className="mt-5 space-y-3">
          <label className="flex items-start gap-2.5 text-sm text-ink-200 cursor-pointer">
            <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} required className="mt-1" />
            <span>{t("I accept the Terms of Service and have read the Privacy Notice.")}</span>
          </label>
          <label className="flex items-start gap-2.5 text-sm text-ink-200 cursor-pointer">
            <input type="checkbox" checked={isAdult} onChange={(e) => setIsAdult(e.target.checked)} className="mt-1" />
            <span>
              {t(AGE_LABEL)}
              <span className="block text-xs text-ink-500 mt-0.5">{t(AGE_HINT)}</span>
            </span>
          </label>
        </div>
        {accept.isError && <p className="text-xs text-signal-blood mt-4">{errorDetail(accept.error)}</p>}
        <button
          type="submit"
          disabled={!accepted || accept.isPending}
          className="mt-6 w-full border border-signal-amber/60 text-signal-amber px-4 py-2 font-mono text-[11px] uppercase tracking-[0.14em] hover:bg-signal-amber/10 disabled:opacity-40"
        >
          {accept.isPending ? t("Saving…") : t("Continue")}
        </button>
        <button
          type="button"
          onClick={signOut}
          className="mt-3 w-full font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 hover:text-ink-200"
        >
          {t("Sign out instead")}
        </button>
      </form>
    </div>
  );
}

export default function TermsGate() {
  const { user, isAuthenticated, setUser } = useAuthStore();
  const { data: fresh } = useQuery({
    queryKey: ["me", user?.id ?? null],
    queryFn: () => auth.me().then((r) => r.data),
    enabled: isAuthenticated,
    retry: false,
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    if (fresh) setUser(fresh);
  }, [fresh, setUser]);

  if (!isAuthenticated || !user?.needs_terms) return null;
  return <TermsPanel initialAdult={!!user.is_adult} />;
}
