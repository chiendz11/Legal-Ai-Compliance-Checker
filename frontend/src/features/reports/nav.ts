import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * Four sections in reading order: the conclusion (with what needs attention), every check,
 * what was read from the contract, and the reviewer's work. Engineering detail is a separate
 * link at the end of the list, not a reading step.
 */
export const TABS = [
  { id: "overview", title: "Tổng quan" },
  { id: "topics", title: "Kết quả kiểm tra" },
  { id: "contract", title: "Hợp đồng" },
  { id: "review", title: "Rà soát và phát hành" },
  { id: "technical", title: "Chi tiết kỹ thuật" },
] as const;

export type TabId = (typeof TABS)[number]["id"];

/** Links saved before the sections were merged keep opening the matching one. */
const LEGACY: Record<string, TabId> = {
  attention: "overview",
  risks: "overview",
  recommendations: "overview",
  compliance: "topics",
  profile: "contract",
  citations: "contract",
  scope: "technical",
  audit: "technical",
};

export type TabTarget = TabId | keyof typeof LEGACY;

function resolve(raw: string | null): TabId | null {
  if (!raw) return null;
  if (TABS.some((t) => t.id === raw)) return raw as TabId;
  return LEGACY[raw] ?? null;
}

/** Section and focused finding live in the URL so a link opens the exact risk/criterion/citation. */
export function useReportNav() {
  const [params, setParams] = useSearchParams();
  const tab: TabId = resolve(params.get("tab")) ?? "overview";
  const focus = params.get("focus");
  const go = useCallback(
    (nextTab: TabTarget, nextFocus?: string) => {
      const next = new URLSearchParams({ tab: resolve(nextTab) ?? "overview" });
      if (nextFocus) next.set("focus", nextFocus);
      const view = params.get("view");
      if (view) next.set("view", view); // keep the split viewer open across sections
      setParams(next);
    },
    [params, setParams],
  );
  const split = params.get("view") === "split";
  const setSplit = useCallback(
    (on: boolean) => {
      const next = new URLSearchParams(params);
      if (on) next.set("view", "split");
      else next.delete("view");
      setParams(next, { replace: true });
    },
    [params, setParams],
  );
  return { tab, focus, go, split, setSplit };
}

export const focusDomId = (id: string) => `focus-${id}`;
