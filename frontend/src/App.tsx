import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "./app/Sidebar";
import { LoginPage } from "./features/auth/LoginPage";
import { CaseListPage } from "./features/cases/CaseListPage";
import { RunPage } from "./features/cases/RunPage";
import { HelpPage } from "./features/help/HelpPage";
import { ReportPage } from "./features/reports/ReportPage";
import { UploadPage } from "./features/upload/UploadPage";
import { useSession } from "./shared/api/queries";
import { isUnauthenticated } from "./shared/auth";
import { Empty } from "./shared/components/ui";

// A 401 while signed in (expired or revoked session) re-checks /auth/me, which brings back the
// login page. Not when already signed out: the session query would refetch itself forever and
// the login form would remount and lose its error.
const recheckSession = (error: unknown) => {
  if (isUnauthenticated(error) && queryClient.getQueryData(["session"]))
    void queryClient.invalidateQueries({ queryKey: ["session"] });
};
const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => query.queryKey[0] !== "session" && recheckSession(error),
  }),
  mutationCache: new MutationCache({ onError: recheckSession }),
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: (count, error) => !isUnauthenticated(error) && count < 1,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AppShell>
          <AuthGate>
            <Routes>
              <Route path="/" element={<CaseListPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/cases/:caId/runs/:runId" element={<RunPage />} />
              <Route path="/reports/:baoCaoId" element={<ReportPage />} />
              <Route path="/help" element={<HelpPage />} />
              <Route path="*" element={<Empty>Không tìm thấy trang.</Empty>} />
            </Routes>
          </AuthGate>
        </AppShell>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

/** Login only when the server says so (401); an offline backend still shows the pages. */
function AuthGate({ children }: { children: ReactNode }) {
  const session = useSession();
  if (isUnauthenticated(session.error)) return <LoginPage />;
  if (session.isPending) return <p className="muted small">Đang kiểm tra phiên đăng nhập…</p>;
  return <>{children}</>;
}
