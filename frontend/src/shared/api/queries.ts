import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";

const ACTIVE = new Set(["QUEUED", "RUNNING"]);

/** Starts a full assessment; a fresh key per click, the server dedupes retries of the same key. */
export function useStartRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (caId: string) =>
      unwrap(
        await api.POST("/api/v1/cases/{ca_id}/runs", {
          params: { path: { ca_id: caId }, header: { "Idempotency-Key": crypto.randomUUID() } },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: ["cases"] }),
  });
}

/** Polls while the run is queued/running; stops once it is COMPLETED or FAILED. */
export function useRunStatus(caId: string, runId: string) {
  return useQuery({
    queryKey: ["run-status", caId, runId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/cases/{ca_id}/runs/{run_id}/status", {
          params: { path: { ca_id: caId, run_id: runId } },
        }),
      ),
    refetchInterval: (query) => (ACTIVE.has(query.state.data?.status ?? "QUEUED") ? 1500 : false),
  });
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => unwrap(await api.GET("/health")),
    retry: false,
    refetchInterval: 30_000,
  });
}

export function useCases(page = 1) {
  return useQuery({
    queryKey: ["cases", page],
    queryFn: async () => unwrap(await api.GET("/api/v1/cases", { params: { query: { page } } })),
  });
}

export function useRunReports(caId: string, runId: string, enabled = true) {
  return useQuery({
    enabled,
    queryKey: ["run-reports", caId, runId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/cases/{ca_id}/runs/{run_id}/reports", {
          params: { path: { ca_id: caId, run_id: runId } },
        }),
      ),
  });
}

export function useReport(baoCaoId: string) {
  return useQuery({
    queryKey: ["report", baoCaoId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/reports/{bao_cao_id}", {
          params: { path: { bao_cao_id: baoCaoId } },
        }),
      ),
  });
}
