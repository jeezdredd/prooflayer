import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import VerifyGate from "./VerifyGate";

interface Props {
  requireVerified?: boolean;
}

export default function ProtectedRoute({ requireVerified = false }: Props) {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requireVerified && user && !user.is_verified) {
    return <VerifyGate />;
  }

  return <Outlet />;
}
