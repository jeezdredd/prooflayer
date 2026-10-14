import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { CLASSROOM_URL, IS_CLASSROOM_APP } from "../appMode";
import VerifyGate from "./VerifyGate";
import Loader from "./ui/Loader";

interface Props {
  requireVerified?: boolean;
}

function classroomTarget(pathname: string): string {
  return pathname.startsWith("/results/") ? `${CLASSROOM_URL}${pathname}` : CLASSROOM_URL;
}

function ToStudentClassroom({ pathname }: { pathname: string }) {
  useEffect(() => {
    window.location.replace(classroomTarget(pathname));
  }, [pathname]);
  return (
    <div className="flex items-center justify-center py-24">
      <Loader />
    </div>
  );
}

export default function ProtectedRoute({ requireVerified = false }: Props) {
  const { isAuthenticated, user } = useAuthStore();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }

  if (user?.student_only && !IS_CLASSROOM_APP) {
    return <ToStudentClassroom pathname={location.pathname} />;
  }

  if (requireVerified && user && !user.is_verified) {
    return <VerifyGate />;
  }

  return <Outlet />;
}
