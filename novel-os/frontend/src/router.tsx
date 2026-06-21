import { AppShell } from "@/components/layout/app-shell";
import { ErrorBoundary } from "@/components/layout/error-boundary";
import { PageLoader } from "@/components/layout/page-loader";
import { StepIndicator } from "@/components/create/step-indicator";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/contexts/auth-context";
import { useAuth } from "@/hooks/use-auth";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, lazy } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Outlet,
  Navigate,
  useParams,
  useLocation,
} from "react-router-dom";

const HomePage = lazy(() =>
  import("@/pages/home-page").then((module) => ({ default: module.HomePage }))
);
const ProjectsPage = lazy(() =>
  import("@/pages/projects-page").then((module) => ({ default: module.ProjectsPage }))
);
const LLMPage = lazy(() =>
  import("@/pages/settings/llm-page").then((module) => ({ default: module.LLMPage }))
);
const CategoryPage = lazy(() =>
  import("@/pages/create/category-page").then((module) => ({ default: module.CategoryPage }))
);
const TopicsPage = lazy(() =>
  import("@/pages/create/topics-page").then((module) => ({ default: module.TopicsPage }))
);
const OutlinePage = lazy(() =>
  import("@/pages/create/outline-page").then((module) => ({ default: module.OutlinePage }))
);
const ConfirmPage = lazy(() =>
  import("@/pages/create/confirm-page").then((module) => ({ default: module.ConfirmPage }))
);
const WritePage = lazy(() =>
  import("@/pages/write/write-page").then((module) => ({ default: module.WritePage }))
);
const DashboardPage = lazy(() =>
  import("@/pages/dashboard/dashboard-page").then((module) => ({ default: module.DashboardPage }))
);
const NotFoundPage = lazy(() =>
  import("@/pages/not-found-page").then((module) => ({ default: module.NotFoundPage }))
);
const LoginPage = lazy(() =>
  import("@/pages/login-page").then((module) => ({ default: module.LoginPage }))
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <PageLoader />;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

function Layout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

function CreateLayout() {
  return (
    <>
      <StepIndicator />
      <Outlet />
    </>
  );
}

function ProjectDetailRedirect() {
  const { id } = useParams<{ id: string }>();
  return <Navigate to={`/projects/${encodeURIComponent(id || "")}/dashboard`} replace />;
}

function ProtectedLayout() {
  return (
    <RequireAuth>
      <Layout />
    </RequireAuth>
  );
}

function LoginRoute() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return <PageLoader />;
  }

  if (user) {
    return <Navigate to="/" replace />;
  }

  return <LoginPage />;
}

export function Router() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Toaster />
          <ErrorBoundary>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/login" element={<LoginRoute />} />
                <Route element={<ProtectedLayout />}>
                  <Route path="/" element={<HomePage />} />
                  <Route path="/projects" element={<ProjectsPage />} />
                  <Route path="/create" element={<Navigate to="/create/category" replace />} />
                  <Route element={<CreateLayout />}>
                    <Route path="/create/category" element={<CategoryPage />} />
                    <Route path="/create/topics" element={<TopicsPage />} />
                    <Route path="/create/outline" element={<OutlinePage />} />
                    <Route path="/create/confirm" element={<ConfirmPage />} />
                  </Route>
                  <Route path="/projects/:id/write" element={<WritePage />} />
                  <Route path="/projects/:id/dashboard" element={<DashboardPage />} />
                  <Route path="/projects/:id" element={<ProjectDetailRedirect />} />
                  <Route path="/settings/llm" element={<LLMPage />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Route>
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
