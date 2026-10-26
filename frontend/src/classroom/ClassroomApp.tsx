import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import Loader from "../components/ui/Loader";
import ProtectedRoute from "../components/ProtectedRoute";
import LoginPage from "../pages/LoginPage";
import RegisterPage from "../pages/RegisterPage";
import { NotFoundPage } from "../pages/ErrorPages";
import ClassroomShell from "./ClassroomShell";
import { useSilentSignIn } from "./useSilentSignIn";

const HubPage = lazy(() => import("./HubPage"));
const OrgPage = lazy(() => import("./OrgPage"));
const SubmitPage = lazy(() => import("./SubmitPage"));
const ClassroomDetailPage = lazy(() => import("../pages/ClassroomDetailPage"));
const ResultPage = lazy(() => import("../pages/ResultPage"));
const BatchPage = lazy(() => import("../pages/BatchPage"));
const VerifyEmailPage = lazy(() => import("../pages/EmailLinkPages").then((m) => ({ default: m.VerifyEmailPage })));
const ConfirmEmailPage = lazy(() => import("../pages/EmailLinkPages").then((m) => ({ default: m.ConfirmEmailPage })));
const AccountPage = lazy(() => import("../pages/AccountPage"));

function Centered() {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-ink-950">
      <Loader />
    </div>
  );
}

export default function ClassroomRoutes() {
  const ready = useSilentSignIn();
  if (!ready) return <Centered />;

  return (
    <Suspense fallback={<Centered />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/confirm-email" element={<ConfirmEmailPage />} />
        <Route element={<ClassroomShell />}>
          <Route path="/:slug" element={<OrgPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<HubPage />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/results/:id" element={<ResultPage />} />
            <Route path="/batches/:id" element={<BatchPage />} />
            <Route path="/c/:id" element={<ClassroomDetailPage />} />
            <Route path="/:slug/c/:id" element={<ClassroomDetailPage />} />
            <Route element={<ProtectedRoute requireVerified />}>
              <Route path="/c/:id/submit" element={<SubmitPage />} />
              <Route path="/:slug/c/:id/submit" element={<SubmitPage />} />
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}
