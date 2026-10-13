import { Link, Outlet, useNavigate } from "react-router-dom";
import { GraduationCap, LogOut } from "lucide-react";
import { useAuthStore } from "../stores/authStore";
import { auth } from "../api/endpoints";

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
              Classroom
            </span>
          </Link>
          <div className="flex items-center gap-4 font-mono text-[11px] text-ink-400">
            {isAuthenticated ? (
              <>
                <span className="hidden sm:inline">{user?.username}</span>
                <button type="button" onClick={signOut} className="hover:text-ink-100" aria-label="Sign out">
                  <LogOut size={14} />
                </button>
              </>
            ) : (
              <Link to="/login" className="hover:text-ink-100 uppercase tracking-[0.14em]">Sign in</Link>
            )}
          </div>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-5 py-10">
        <Outlet />
      </main>
    </div>
  );
}
