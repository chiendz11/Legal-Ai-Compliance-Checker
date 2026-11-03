import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation } from "react-router-dom";

import { LoginPage } from "./features/auth/LoginPage";
import { CaseListPage } from "./features/cases/CaseListPage";
import { RunPage } from "./features/cases/RunPage";
import { ReportPage } from "./features/reports/ReportPage";
import { UploadPage } from "./features/upload/UploadPage";
import { useHealth, useLogout, useSession } from "./shared/api/queries";
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
    queries: { staleTime: 60_000, retry: (count, error) => !isUnauthenticated(error) && count < 1 },
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

function pageTitle(path: string) {
  if (path === "/upload") return "Tải hợp đồng";
  if (path.startsWith("/cases/")) return "Tiến độ đánh giá";
  if (path.startsWith("/reports/")) return "Báo cáo đánh giá";
  return "Lịch sử đánh giá";
}

/** Fixed sidebar (off-canvas under 1024px), sticky top bar, centered page content. */
function Shell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [pathname]);
  return (
    <div className="app">
      <Sidebar open={open} />
      <div className={`scrim${open ? " show" : ""}`} onClick={() => setOpen(false)} />
      <div className="main">
        <TopBar title={pageTitle(pathname)} onMenu={() => setOpen(!open)} />
        <main className="page">{children}</main>
      </div>
    </div>
  );
}

function Sidebar({ open }: { open: boolean }) {
  const can = useCan();
  return (
    <aside className={`sidebar${open ? " open" : ""}`} aria-label="Điều hướng chính">
      <Link to="/" className="brand">
        <span className="brand-mark">
          <Icon name="scale" />
        </span>
        <span>
          <div className="brand-name">Legal Checker</div>
          <div className="brand-sub">Kiểm tra tuân thủ hợp đồng</div>
        </span>
      </Link>
      <nav className="nav">
        <div className="nav-label">Đánh giá</div>
        <NavLink to="/" end>
          <Icon name="history" />
          Lịch sử
        </NavLink>
        {can("uploader") && (
          <NavLink to="/upload">
            <Icon name="upload" />
            Tải hợp đồng
          </NavLink>
        )}
      </nav>
      <UserMenu />
    </aside>
  );
}

function TopBar({ title, onMenu }: { title: string; onMenu: () => void }) {
  const health = useHealth();
  const online = health.data?.status === "ok";
  return (
    <header className="topbar">
      <button
        type="button"
        className="button ghost icon menu-btn"
        aria-label="Mở menu"
        onClick={onMenu}
      >
        <Icon name="menu" />
      </button>
      <span className="topbar-title">{title}</span>
      <div className="topbar-meta">
        {mockEnabled && <span className="badge tone-info">Mock API</span>}
        <span
          className={`badge tone-${online ? "good" : health.isPending ? "neutral" : "bad"}`}
          title={health.data ? `schema ${health.data.schema_version}` : undefined}
        >
          Backend {online ? "online" : health.isPending ? "…" : "offline"}
        </span>
      </div>
    </header>
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
    <div className="side-foot">
      <span className="avatar" aria-hidden="true">
        {initials}
      </span>
      <div className="side-user" title={`${data.actor_id} · ${data.tenant_id}`}>
        <div className="n">{data.display_name}</div>
        <div className="e">{data.roles.join(", ") || "không có quyền"}</div>
      </div>
      {signedIn(data) ? (
        <button
          type="button"
          className="button ghost icon"
          aria-label="Đăng xuất"
          title="Đăng xuất"
          disabled={logout.isPending}
          onClick={() => logout.mutate()}
        >
          <Icon name="logout" />
        </button>
      ) : (
        <span className="badge tone-neutral" title="AUTH_MODE=off: tài khoản dev, đủ mọi quyền">
          dev
        </span>
      )}
    </div>
  );
}
