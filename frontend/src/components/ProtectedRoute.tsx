import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import VerifyGate from "./VerifyGate";

interface Props {
  requireVerified?: boolean;
}

export default function ProtectedRoute({ requireVerified = false }: Props) {
  const { isAuthenticated, user } = useAuthStore();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }

  if (requireVerified && user && !user.is_verified) {
    return <VerifyGate />;
  }

  return <Outlet />;
}
