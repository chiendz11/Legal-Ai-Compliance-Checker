import { http, HttpResponse } from "msw";

import type { CaseRecord, Page, ReportRecord } from "../shared/api/client";

// Lazy so each ~600 KB fixture loads only when a mocked route needs it.
const fixtureModules = import.meta.glob<ReportRecord>("./fixtures/*.json", { import: "default" });

let cache: Promise<ReportRecord[]> | undefined;
function fixtures() {
  cache ??= Promise.all(Object.values(fixtureModules).map((load) => load()));
  return cache;
}

function page<T>(items: T[], url: URL): Page<T> {
  const pageNumber = Number(url.searchParams.get("page") ?? 1);
  const pageSize = Number(url.searchParams.get("page_size") ?? 20);
  const start = (pageNumber - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    page: pageNumber,
    page_size: pageSize,
    total: items.length,
  };
}

function notFound(message: string) {
  return HttpResponse.json(
    { error: { code: "NOT_FOUND", message, details: [] } },
    { status: 404 },
  );
}

/** Mocks only planned (NOT_IMPLEMENTED) routes; implemented ones pass through to the backend. */
export const handlers = [
  http.get("/api/v1/cases", async ({ request }) => {
    const records: CaseRecord[] = (await fixtures()).map((record) => ({
      case: record.report.report_json.case,
      latest_run_id: record.run_id,
      latest_run_status: "COMPLETED",
    }));
    return HttpResponse.json(page(records, new URL(request.url)));
  }),

  http.get("/api/v1/cases/:caId/runs/:runId/reports", async ({ params, request }) => {
    const items = (await fixtures()).filter(
      (record) => record.report.ca_id === params.caId && record.run_id === params.runId,
    );
    if (!items.length) return notFound("Run not found in permitted scope");
    return HttpResponse.json(page(items, new URL(request.url)));
  }),

  http.get("/api/v1/reports/:baoCaoId", async ({ params }) => {
    const record = (await fixtures()).find((r) => r.report.bao_cao_id === params.baoCaoId);
    return record ? HttpResponse.json(record) : notFound("Report not found in permitted scope");
  }),
];

export const fixtureCount = Object.keys(fixtureModules).length;
