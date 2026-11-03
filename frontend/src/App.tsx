import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { BrowserRouter, Link, NavLink, Route, Routes, useMatch } from "react-router-dom";

import { LoginPage } from "./features/auth/LoginPage";
import { CaseListPage } from "./features/cases/CaseListPage";
import { RunPage } from "./features/cases/RunPage";
import { ReportPage } from "./features/reports/ReportPage";
import { UploadPage } from "./features/upload/UploadPage";
import { useHealth, useLogout, useReport, useSession } from "./shared/api/queries";
import { isUnauthenticated, signedIn, useCan, useCurrentSession } from "./shared/auth";
import { Icon } from "./shared/components/icons";
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
        <Shell>
          <AuthGate>
            <Routes>
              <Route path="/" element={<CaseListPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/cases/:caId/runs/:runId" element={<RunPage />} />
              <Route path="/reports/:baoCaoId" element={<ReportPage />} />
              <Route path="*" element={<Empty>Không tìm thấy trang.</Empty>} />
            </Routes>
          </AuthGate>
        </Shell>
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

/**
 * The object being viewed (a run or a report) opens as its own tab next to the fixed ones,
 * named after the case/contract, and closes back to the history like a browser tab.
 */
function ContextTab() {
  const run = useMatch("/cases/:caId/runs/:runId");
  const report = useMatch("/reports/:baoCaoId");
  const reportId = report?.params.baoCaoId ?? "";
  const { data } = useReport(reportId, !!report);
  if (!run && !report) return null;
  const label = run
    ? `Run · ${run.params.caId}`
    : `Báo cáo · ${data?.report.report_json.case.hop_dong_id ?? "…"}`;
  return (
    <span className="wtab on" aria-current="page">
      <Icon name={run ? "activity" : "book"} />
      <span className="wtab-label">{label}</span>
      <Link to="/" className="x" aria-label="Đóng, về lịch sử" title="Đóng">
        <Icon name="x" />
      </Link>
    </span>
  );
}

/** Rounded window on a canvas: top bar with browser-like tabs, then the content surface. */
function Shell({ children }: { children: ReactNode }) {
  const can = useCan();
  const tabClass = ({ isActive }: { isActive: boolean }) => (isActive ? "wtab on" : "wtab");
  return (
    <div className="window">
      <header className="wbar">
        <Link to="/" className="logo" aria-label="Legal Checker">
          <span className="logo-mark">
            <i />
          </span>
          <span>Legal Checker</span>
        </Link>
        <nav className="wtabs" aria-label="Điều hướng chính">
          <NavLink to="/" end className={tabClass}>
            <Icon name="history" />
            Lịch sử
          </NavLink>
          {can("uploader") && (
            <NavLink to="/upload" className={tabClass}>
              <Icon name="upload" />
              Tải hợp đồng
            </NavLink>
          )}
          <ContextTab />
        </nav>
        <div className="wspacer" />
        <div className="wmeta">
          <BackendStatus />
          <UserMenu />
        </div>
      </header>
      <div className="surface">
        <main className="view">{children}</main>
      </div>
    </div>
  );
}

function BackendStatus() {
  const health = useHealth();
  const online = health.data?.status === "ok";
  return (
    <>
      {mockEnabled && <span className="badge tone-info">Mock API</span>}
      <span
        className={`badge tone-${online ? "good" : health.isPending ? "neutral" : "bad"}`}
        title={health.data ? `schema ${health.data.schema_version}` : undefined}
      >
        Backend {online ? "online" : health.isPending ? "…" : "offline"}
      </span>
    </>
  );
}

function UserMenu() {
  const data = useCurrentSession();
  const logout = useLogout();
  if (!data) return null;
  const initials = data.display_name
    .split(/\s+/)
    .map((word) => word[0])
    .slice(-2)
    .join("")
    .toUpperCase();
  return (
    <>
      <span
        className="who"
        title={`${data.actor_id} · ${data.tenant_id} · ${data.roles.join(", ") || "không có quyền"}`}
      >
        <b>{data.display_name}</b>
        <span>{signedIn(data) ? `${data.roles.length} vai trò` : "Chế độ dev · đủ quyền"}</span>
      </span>
      <span className="av" aria-hidden="true">
        {initials}
      </span>
      {signedIn(data) && (
        <button
          type="button"
          className="circle-btn solid"
          aria-label="Đăng xuất"
          title="Đăng xuất"
          disabled={logout.isPending}
          onClick={() => logout.mutate()}
        >
          <Icon name="logout" />
        </button>
      )}
    </>
  );
}
