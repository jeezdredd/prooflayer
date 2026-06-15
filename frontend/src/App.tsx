import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuthStore } from "./stores/authStore";
import { useVisitTracking } from "./hooks/useVisitTracking";
import Loader from "./components/ui/Loader";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import LandingPage from "./pages/LandingPage";
import { ToastContainer } from "./components/ui/Toast";
import ConsentBanner from "./components/ConsentBanner";

const UploadPage = lazy(() => import("./pages/UploadPage"));
const ResultPage = lazy(() => import("./pages/ResultPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const FactCheckPage = lazy(() => import("./pages/FactCheckPage"));
const CommunityFakesPage = lazy(() => import("./pages/CommunityFakesPage"));
const ComparePage = lazy(() => import("./pages/ComparePage"));
const EmbedPage = lazy(() => import("./pages/EmbedPage"));
const ReviewQueuePage = lazy(() => import("./pages/ReviewQueuePage"));
const StatusPage = lazy(() => import("./pages/StatusPage"));
const CreditsPage = lazy(() => import("./pages/CreditsPage"));
const VerifyEmailPage = lazy(() => import("./pages/VerifyEmailPage"));

function PageLoader() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/80 backdrop-blur-sm">
      <Loader />
    </div>
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

function AppRoutes() {
  const { hydrate } = useAuthStore();
  useVisitTracking();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/community-fakes" element={<CommunityFakesPage />} />
            <Route path="/embed" element={<EmbedPage />} />
            <Route path="/results/:id" element={<ResultPage />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="/credits" element={<CreditsPage />} />
            <Route element={<ProtectedRoute requireVerified />}>
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/compare" element={<ComparePage />} />
              <Route path="/review" element={<ReviewQueuePage />} />
              <Route path="/factcheck" element={<FactCheckPage />} />
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
        <ToastContainer />
        <ConsentBanner />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
