import { Link, Outlet, useNavigate } from "react-router-dom";
import { ArrowLeft, GraduationCap, LogOut, UserRound } from "lucide-react";
import { useAuthStore } from "../stores/authStore";
import { auth } from "../api/endpoints";
import TermsGate from "../components/TermsGate";
import LangSwitch from "../components/LangSwitch";
import { t } from "../i18n";
import { MAIN_URL } from "./shared";
import StatusPulse from "./StatusPulse";

export default function ClassroomShell() {
  const { user, isAuthenticated, logout } = useAuthStore();
  const navigate = useNavigate();

  const signOut = async () => {
    try {
      await auth.logout();
    } finally {
      logout();
      navigate("/login");
    }
  };

  return (
    <div className="min-h-screen bg-ink-950 text-ink-100">
      <header className="border-b border-[var(--line-strong)]">
        <div className="max-w-6xl mx-auto px-5 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <GraduationCap size={18} className="text-signal-sage" />
            <span className="font-display text-xl text-ink-50">
              Proof<span className="italic text-iris">Layer</span>
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink-500 border-l border-[var(--line-strong)] pl-2.5">
              {t("Classroom")}
            </span>
          </Link>
          <div className="flex items-center gap-3 sm:gap-4 font-mono text-[11px] text-ink-400">
            <StatusPulse />
            {!user?.student_only && (
              <a
                href={isAuthenticated ? `${MAIN_URL}/dashboard` : MAIN_URL}
                className="flex items-center gap-1.5 hover:text-ink-100 uppercase tracking-[0.14em]"
                title={t("Back to ProofLayer")}
              >
                <ArrowLeft size={13} />
                <span className="hidden sm:inline">{t("ProofLayer")}</span>
              </a>
            )}
            <LangSwitch />
            {isAuthenticated ? (
              <>
                <Link to="/account" className="flex items-center gap-1.5 hover:text-ink-100" title={t("Account & privacy")} aria-label={t("Account & privacy")}>
                  <UserRound size={14} />
                  <span className="hidden sm:inline">{user?.username}</span>
                </Link>
                <button type="button" onClick={signOut} className="hover:text-ink-100" aria-label={t("Sign out")}>
                  <LogOut size={14} />
                </button>
              </>
            ) : (
              <Link to="/login" className="hover:text-ink-100 uppercase tracking-[0.14em]">{t("Sign in")}</Link>
            )}
          </div>
        </div>
      </header>
      <TermsGate />
      <main className="max-w-6xl mx-auto px-5 py-10">
        <Outlet />
      </main>
    </div>
  );
}
