import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";

export default function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link to="/upload" className="text-xl font-bold text-gray-900">
              ProofLayer
            </Link>
            <NavLink
              to="/upload"
              className={({ isActive }) =>
                isActive ? "text-sm font-medium text-gray-900" : "text-sm text-gray-500 hover:text-gray-900"
              }
            >
              Verify
            </NavLink>
            <NavLink
              to="/dashboard"
              className={({ isActive }) =>
                isActive ? "text-sm font-medium text-gray-900" : "text-sm text-gray-500 hover:text-gray-900"
              }
            >
              Dashboard
            </NavLink>
            <NavLink
              to="/factcheck"
              className={({ isActive }) =>
                isActive ? "text-sm font-medium text-gray-900" : "text-sm text-gray-500 hover:text-gray-900"
              }
            >
              Fact Check
            </NavLink>
            <NavLink
              to="/community-fakes"
              className={({ isActive }) =>
                isActive ? "text-sm font-medium text-gray-900" : "text-sm text-gray-500 hover:text-gray-900"
              }
            >
              Community Fakes
            </NavLink>
            <NavLink
              to="/compare"
              className={({ isActive }) =>
                isActive ? "text-sm font-medium text-gray-900" : "text-sm text-gray-500 hover:text-gray-900"
              }
            >
              Compare
            </NavLink>
            <NavLink
              to="/embed"
              className={({ isActive }) =>
                isActive ? "text-sm font-medium text-gray-900" : "text-sm text-gray-500 hover:text-gray-900"
              }
            >
              Embed
            </NavLink>
            {user?.is_staff && (
              <NavLink
                to="/review"
                className={({ isActive }) =>
                  isActive ? "text-sm font-medium text-purple-700" : "text-sm text-purple-600 hover:text-purple-800"
                }
              >
                Review
              </NavLink>
            )}
          </div>
          {user && (
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600">{user.email}</span>
              <button
                onClick={handleLogout}
                className="text-sm text-red-600 hover:text-red-800"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </nav>
      <main className="max-w-5xl mx-auto px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
