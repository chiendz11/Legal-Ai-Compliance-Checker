import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";

import { LoginPage } from "./features/auth/LoginPage";
import { CaseListPage } from "./features/cases/CaseListPage";
import { RunPage } from "./features/cases/RunPage";
import { ReportPage } from "./features/reports/ReportPage";
import { UploadPage } from "./features/upload/UploadPage";
import { useHealth, useLogout, useSession } from "./shared/api/queries";
import { isUnauthenticated, signedIn, useCan, useCurrentSession } from "./shared/auth";
import { Empty } from "./shared/components/ui";
import { mockEnabled } from "./shared/env";

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
    queries: { staleTime: 60_000, retry: (count, error) => !isUnauthenticated(error) && count < 1 },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <TopBar />
        <main className="page">
          <AuthGate>
            <Routes>
              <Route path="/" element={<CaseListPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/cases/:caId/runs/:runId" element={<RunPage />} />
              <Route path="/reports/:baoCaoId" element={<ReportPage />} />
              <Route path="*" element={<Empty>Không tìm thấy trang.</Empty>} />
            </Routes>
          </AuthGate>
        </main>
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

function TopBar() {
  const health = useHealth();
  const online = health.data?.status === "ok";
  const can = useCan();
  return (
    <header className="topbar">
      <Link to="/" className="brand">
        Legal Compliance Checker
      </Link>
      <nav className="topnav" aria-label="Điều hướng chính">
        <NavLink to="/" end>
          Lịch sử
        </NavLink>
        {can("uploader") && <NavLink to="/upload">Tải hợp đồng</NavLink>}
      </nav>
      <div className="topbar-meta">
        {mockEnabled && <span className="badge tone-info">Mock API</span>}
        <span
          className={`badge tone-${online ? "good" : health.isPending ? "neutral" : "bad"}`}
          title={health.data ? `schema ${health.data.schema_version}` : undefined}
        >
          Backend {online ? "online" : health.isPending ? "…" : "offline"}
        </span>
        <UserMenu />
      </div>
    </header>
  );
}

function UserMenu() {
  const data = useCurrentSession();
  const logout = useLogout();
  if (!data) return null;
  return (
    <span className="user-menu small">
      <span title={`${data.actor_id} · ${data.tenant_id}`}>
        {data.display_name}
        <span className="muted"> · {data.roles.join(", ") || "không có quyền"}</span>
      </span>
      {signedIn(data) ? (
        <button
          type="button"
          className="button"
          disabled={logout.isPending}
          onClick={() => logout.mutate()}
        >
          Đăng xuất
        </button>
      ) : (
        <span className="badge tone-neutral" title="AUTH_MODE=off: tài khoản dev, đủ mọi quyền">
          dev
        </span>
      )}
    </span>
  );
}
