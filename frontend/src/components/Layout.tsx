import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { motion, AnimatePresence } from "motion/react";
import clsx from "clsx";
import { useState } from "react";
import {
  Upload, LayoutDashboard, ScrollText, Users, GitCompareArrows,
  Code2, Activity, Shield, LogOut, Home, Menu, X,
} from "lucide-react";
import ShaderBackground from "./ui/ShaderBackground";
import EmailVerifyBanner from "./EmailVerifyBanner";

interface NavItem {
  to: string;
  label: string;
  code: string;
  Icon: typeof Upload;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/upload", label: "Verify", code: "01", Icon: Upload },
  { to: "/dashboard", label: "Dashboard", code: "02", Icon: LayoutDashboard },
  { to: "/factcheck", label: "Fact Check", code: "03", Icon: ScrollText },
  { to: "/community-fakes", label: "Community", code: "04", Icon: Users },
  { to: "/compare", label: "Compare", code: "05", Icon: GitCompareArrows },
  { to: "/embed", label: "Embed", code: "06", Icon: Code2 },
  { to: "/status", label: "Status", code: "07", Icon: Activity },
];

function Time() {
  const t = new Date();
  return (
    <span className="ticker">
      {String(t.getUTCHours()).padStart(2, "0")}:{String(t.getUTCMinutes()).padStart(2, "0")} UTC
    </span>
  );
}

function NavRail({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuthStore();
  return (
    <>
      <Link
        to="/"
        onClick={onNavigate}
        className="flex items-end gap-2 px-5 py-5 group"
        title="Back to landing"
      >
        <span className="font-display text-[1.6rem] leading-none text-ink-50 tracking-tight">
          Proof<span className="italic text-iris">Layer</span>
        </span>
      </Link>

      <Link
        to="/"
        onClick={onNavigate}
        className="mx-3 mb-4 px-3 py-2 flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 hover:text-signal-amber transition-colors group rounded-sm"
      >
        <Home size={14} strokeWidth={1.5} />
        <span>Landing</span>
        <span className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
      </Link>

      <div className="px-5 mb-3">
        <div className="hairline" />
        <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-600 mt-3">
          Pipeline
        </div>
      </div>

      <nav className="flex-1 px-3 space-y-0.5 relative">
        {NAV_ITEMS.map((item) => {
          const Icon = item.Icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onNavigate}
              className={({ isActive }) =>
                clsx(
                  "group relative flex items-center gap-3 px-3 py-2.5 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors rounded-sm",
                  isActive
                    ? "text-ink-50"
                    : "text-ink-500 hover:text-ink-100 hover:bg-white/[0.03]",
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span
                      layoutId="nav-indicator"
                      className="absolute left-0 top-1/2 -translate-y-1/2 w-px h-5 bg-signal-amber"
                      transition={{ type: "spring", stiffness: 400, damping: 30 }}
                    />
                  )}
                  <span className={clsx("text-ink-700", isActive && "text-signal-amber")}>
                    <Icon size={16} strokeWidth={1.5} />
                  </span>
                  <span className="text-ink-700 mr-1">{item.code}</span>
                  <span>{item.label}</span>
                </>
              )}
            </NavLink>
          );
        })}
        {user?.is_staff && (
          <NavLink
            to="/review"
            onClick={onNavigate}
            className={({ isActive }) =>
              clsx(
                "group relative flex items-center gap-3 px-3 py-2.5 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors rounded-sm",
                isActive
                  ? "text-signal-violet"
                  : "text-signal-violet/60 hover:text-signal-violet hover:bg-signal-violet/[0.05]",
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId="nav-indicator"
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-px h-5 bg-signal-violet"
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
                <Shield size={16} strokeWidth={1.5} />
                <span className="text-ink-700 mr-1">08</span>
                <span>Review</span>
              </>
            )}
          </NavLink>
        )}
      </nav>
    </>
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
            Agent
          </span>
        </div>
        <div className="font-mono text-xs text-ink-200 truncate" title={user.email}>
          {user.email}
        </div>
        <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-600 mt-2 ticker">
          CASE/{caseId} · <Time />
        </div>
      </div>
      <motion.button
        onClick={onLogout}
        className="w-full flex items-center justify-center gap-2 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.14em] border border-white/8 hover:border-signal-blood/40 hover:text-signal-blood text-ink-300 transition-colors rounded-sm"
        whileTap={{ scale: 0.98 }}
      >
        <LogOut size={13} strokeWidth={1.5} />
        Logout
      </motion.button>
    </div>
  );
}

export default function Layout() {
  const { logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen text-ink-100 relative">
      <ShaderBackground variant="noir" />

      {/* MOBILE HAMBURGER BAR */}
      <div className="lg:hidden sticky top-0 z-40 backdrop-blur-xl bg-ink-950/85 border-b border-white/5 h-14 flex items-center justify-between px-4 relative">
        <Link to="/" className="font-display text-2xl text-ink-50 leading-none">
          Proof<span className="italic text-iris">Layer</span>
        </Link>
        <button
          onClick={() => setMobileOpen((v) => !v)}
          className="text-ink-200 p-1.5"
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* SIDEBAR (desktop) */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 w-[240px] z-40 backdrop-blur-xl bg-ink-950/85 border-r border-white/5 flex-col">
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
              className="fixed inset-y-0 left-0 z-50 w-[260px] bg-ink-950 border-r border-white/8 flex flex-col lg:hidden"
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
