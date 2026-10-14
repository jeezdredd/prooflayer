import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { motion, AnimatePresence } from "motion/react";
import clsx from "clsx";
import { useState } from "react";
import {
  Upload, LayoutDashboard, ScrollText, Users, GitCompareArrows,
  Code2, Activity, Shield, LogOut, Menu, X, Layers, Globe, CreditCard, KeyRound, GraduationCap, Settings,
} from "lucide-react";
import ShaderBackground from "./ui/ShaderBackground";
import EmailVerifyBanner from "./EmailVerifyBanner";
import TermsGate from "./TermsGate";
import { FeedbackModal, FeedbackTrigger } from "./FeedbackModal";
import LangSwitch from "./LangSwitch";
import { msg, t } from "../i18n";

interface NavItem {
  to: string;
  label: string;
  Icon: typeof Upload;
}

const NAV_GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: msg("Checks"),
    items: [
      { to: "/upload", label: msg("Verify"), Icon: Upload },
      { to: "/dashboard", label: msg("Dashboard"), Icon: LayoutDashboard },
      { to: "/factcheck", label: msg("Fact Check"), Icon: ScrollText },
      { to: "/compare", label: msg("Compare"), Icon: GitCompareArrows },
    ],
  },
  {
    title: msg("Education"),
    items: [{ to: "/classroom", label: msg("Classroom"), Icon: GraduationCap }],
  },
  {
    title: msg("Community"),
    items: [
      { to: "/feed", label: msg("Public Feed"), Icon: Globe },
      { to: "/community-fakes", label: msg("Known fakes"), Icon: Users },
    ],
  },
  {
    title: msg("For developers"),
    items: [
      { to: "/developers", label: msg("API"), Icon: KeyRound },
      { to: "/embed", label: msg("Embed"), Icon: Code2 },
    ],
  },
  {
    title: msg("Service"),
    items: [
      { to: "/pricing", label: msg("Pricing"), Icon: CreditCard },
      { to: "/status", label: msg("Status"), Icon: Activity },
      { to: "/stack", label: msg("Stack"), Icon: Layers },
    ],
  },
];

const ADMIN_URL = `${(import.meta.env.VITE_API_URL || "").replace(/\/api\/v1\/?$/, "")}/admin/`;

function NavItemLink({ item, onNavigate, staff }: { item: NavItem; onNavigate?: () => void; staff?: boolean }) {
  const Icon = item.Icon;
  return (
    <NavLink
      to={item.to}
      onClick={onNavigate}
      className={({ isActive }) =>
        clsx(
          "group relative flex items-center gap-3 px-3 py-[7px] text-[13px] rounded-md transition-colors",
          isActive
            ? staff ? "text-signal-violet bg-signal-violet/[0.08]" : "text-ink-50 bg-white/[0.06]"
            : staff ? "text-signal-violet/70 hover:text-signal-violet hover:bg-signal-violet/[0.05]" : "text-ink-300 hover:text-ink-50 hover:bg-white/[0.04]",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              layoutId="nav-indicator"
              className={clsx("absolute left-0 inset-y-1.5 w-[2px] rounded-r-sm", staff ? "bg-signal-violet" : "bg-signal-amber")}
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
            />
          )}
          <Icon size={15} strokeWidth={1.6} className={clsx("shrink-0", isActive ? (staff ? "text-signal-violet" : "text-signal-amber") : "text-ink-500 group-hover:text-ink-300")} />
          <span className="truncate">{t(item.label)}</span>
        </>
      )}
    </NavLink>
  );
}

function NavRail({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuthStore();
  return (
    <>
      <Link to="/" onClick={onNavigate} className="flex items-end gap-2 px-5 pt-5 pb-4" title={t("Back to landing")}>
        <span className="font-display text-[1.6rem] leading-none text-ink-50 tracking-tight">
          Proof<span className="italic text-iris">Layer</span>
        </span>
      </Link>

      <nav className="nav-scroll flex-1 min-h-0 overflow-y-auto px-3 pb-3 space-y-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.title}>
            <div className="px-3 mb-1 font-mono text-[9px] uppercase tracking-[0.2em] text-ink-400">{t(group.title)}</div>
            <div className="space-y-px">
              {group.items.map((item) => <NavItemLink key={item.to} item={item} onNavigate={onNavigate} />)}
            </div>
          </div>
        ))}
        {user?.is_staff && (
          <div>
            <div className="px-3 mb-1 font-mono text-[9px] uppercase tracking-[0.2em] text-signal-violet/60">{t("Staff")}</div>
            <div className="space-y-px">
              <NavItemLink item={{ to: "/review", label: msg("Review"), Icon: Shield }} onNavigate={onNavigate} staff />
              <a
                href={ADMIN_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center gap-3 px-3 py-[7px] text-[13px] rounded-md text-signal-violet/70 hover:text-signal-violet hover:bg-signal-violet/[0.05] transition-colors"
              >
                <Settings size={15} strokeWidth={1.6} className="shrink-0" />
                <span className="truncate">{t("Admin panel")}</span>
                <span className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
              </a>
            </div>
          </div>
        )}
      </nav>
    </>
  );
}

function Time() {
  const now = new Date();
  return (
    <span className="ticker">
      {String(now.getUTCHours()).padStart(2, "0")}:{String(now.getUTCMinutes()).padStart(2, "0")} UTC
    </span>
  );
}

function AgentFooter({ onLogout }: { onLogout: () => void }) {
  const { user } = useAuthStore();
  const date = new Date();
  const caseId = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}${String(date.getDate()).padStart(2, "0")}`;

  if (!user) return null;
  return (
    <div className="px-3 pb-4 pt-3 border-t border-white/5">
      <div className="px-3 py-3 mb-2 rounded-sm bg-white/[0.02] border border-white/5">
        <div className="flex items-center gap-2 mb-1">
          <span className="w-1.5 h-1.5 rounded-full bg-signal-sage pulse-dot" />
          <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500">
            {t("Agent")}
          </span>
        </div>
        <div className="font-mono text-xs text-ink-200 truncate" title={user.email}>
          {user.email}
        </div>
        <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-600 mt-2 ticker">
          CASE/{caseId} · <Time />
        </div>
        <Link to="/account" className="mt-2 inline-block font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500 hover:text-signal-amber">
          {t("Account & privacy")} →
        </Link>
      </div>
      <motion.button
        onClick={onLogout}
        className="w-full flex items-center justify-center gap-2 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.14em] border border-white/10 hover:border-signal-blood/40 hover:text-signal-blood text-ink-300 transition-colors rounded-sm"
        whileTap={{ scale: 0.98 }}
      >
        <LogOut size={13} strokeWidth={1.5} />
        {t("Logout")}
      </motion.button>
      <div className="mt-3 flex justify-center"><LangSwitch /></div>
    </div>
  );
}

export default function Layout() {
  const { logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  const handleLogout = async () => {
    try {
      const { auth } = await import("../api/endpoints");
      await auth.logout();
    } catch {
      // ignore
    }
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen text-ink-100 relative">
      <ShaderBackground variant="noir" />

      {/* MOBILE HAMBURGER BAR */}
      <div className="lg:hidden sticky top-0 z-40 backdrop-blur-xl bg-ink-950/50 border-b border-white/5 h-14 flex items-center justify-between px-4 relative">
        <Link to="/" className="font-display text-2xl text-ink-50 leading-none">
          Proof<span className="italic text-iris">Layer</span>
        </Link>
        <LangSwitch className="ml-auto mr-3" />
        <button
          onClick={() => setMobileOpen((v) => !v)}
          className="text-ink-200 p-1.5"
          aria-label={t("Toggle menu")}
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* SIDEBAR (desktop) */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 w-[240px] z-40 backdrop-blur-xl bg-ink-950/50 border-r border-white/5 flex-col">
        <NavRail />
        <AgentFooter onLogout={handleLogout} />
      </aside>

      {/* SIDEBAR (mobile drawer) */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-ink-950/60 backdrop-blur-sm lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              className="fixed inset-y-0 left-0 z-50 w-[260px] bg-ink-950 border-r border-white/10 flex flex-col lg:hidden"
              initial={{ x: -260 }}
              animate={{ x: 0 }}
              exit={{ x: -260 }}
              transition={{ type: "spring", stiffness: 260, damping: 28 }}
            >
              <NavRail onNavigate={() => setMobileOpen(false)} />
              <AgentFooter onLogout={handleLogout} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <TermsGate />
      <FeedbackModal open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
      {!feedbackOpen && <FeedbackTrigger onClick={() => setFeedbackOpen(true)} />}

      {/* MAIN */}
      <main className="lg:pl-[240px] relative z-10">
        <div className="max-w-[1280px] mx-auto px-6 lg:px-12 py-10 lg:py-14">
          <EmailVerifyBanner />
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
