import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { api, type RunProgress, unwrap } from "./client";

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

/**
 * Live run progress: Server-Sent Events push each change; if the stream is unavailable or
 * drops, the query polls /status while the run is queued/running. Both stop at COMPLETED/FAILED.
 */
export function useRunStatus(caId: string, runId: string) {
  const client = useQueryClient();
  const queryKey = useMemo(() => ["run-status", caId, runId], [caId, runId]);
  const [live, setLive] = useState(false);

  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const url = `/api/v1/cases/${encodeURIComponent(caId)}/runs/${encodeURIComponent(runId)}/events`;
    const source = new EventSource(url);
    source.addEventListener("progress", (event) => {
      setLive(true);
      client.setQueryData(queryKey, JSON.parse((event as MessageEvent<string>).data) as RunProgress);
    });
    // The server closes the stream when the run ends; the browser would then reconnect.
    source.onerror = () => {
      source.close();
      setLive(false);
    };
    return () => source.close();
  }, [caId, runId, client, queryKey]);

  return useQuery({
    queryKey,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/cases/{ca_id}/runs/{run_id}/status", {
          params: { path: { ca_id: caId, run_id: runId } },
        }),
      ),
    refetchInterval: (query) =>
      !live && ACTIVE.has(query.state.data?.status ?? "QUEUED") ? 1500 : false,
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

/** Names for the report's legal-basis IDs, from the knowledge snapshot the report pinned. */
export function useLegalBasis(baoCaoId: string) {
  return useQuery({
    queryKey: ["legal-basis", baoCaoId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/reports/{bao_cao_id}/legal-basis", {
          params: { path: { bao_cao_id: baoCaoId } },
        }),
      ),
    staleTime: Infinity,
    retry: false,
  });
}

/** Pinned run inputs/outputs (chunks for the evidence viewer); fetched only when needed. */
export function useRunResults(caId: string, runId: string, enabled: boolean) {
  return useQuery({
    enabled,
    queryKey: ["run-results", caId, runId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/cases/{ca_id}/runs/{run_id}/results", {
          params: { path: { ca_id: caId, run_id: runId } },
        }),
      ),
    staleTime: Infinity,
    retry: false,
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
