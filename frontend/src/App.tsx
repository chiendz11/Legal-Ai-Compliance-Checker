import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { CaseListPage } from "./features/cases/CaseListPage";
import { RunPage } from "./features/cases/RunPage";
import { ReportPage } from "./features/reports/ReportPage";
import { useHealth } from "./shared/api/queries";
import { Empty } from "./shared/components/ui";
import { mockEnabled } from "./shared/env";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: 1 } },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <TopBar />
        <main className="page">
          <Routes>
            <Route path="/" element={<CaseListPage />} />
            <Route path="/cases/:caId/runs/:runId" element={<RunPage />} />
            <Route path="/reports/:baoCaoId" element={<ReportPage />} />
            <Route path="*" element={<Empty>Không tìm thấy trang.</Empty>} />
          </Routes>
        </main>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function TopBar() {
  const health = useHealth();
  const online = health.data?.status === "ok";
  return (
    <header className="topbar">
      <Link to="/" className="brand">
        Legal Compliance Checker
      </Link>
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
