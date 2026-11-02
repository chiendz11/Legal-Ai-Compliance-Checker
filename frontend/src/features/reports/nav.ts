import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

export const TABS = [
  { id: "profile", title: "Hồ sơ hợp đồng" },
  { id: "scope", title: "Phạm vi pháp lý" },
  { id: "compliance", title: "Tuân thủ" },
  { id: "citations", title: "Viện dẫn" },
  { id: "risks", title: "Rủi ro" },
  { id: "recommendations", title: "Khuyến nghị" },
  { id: "review", title: "Rà soát" },
  { id: "audit", title: "Audit" },
] as const;

export type TabId = (typeof TABS)[number]["id"];

/** Tab and focused finding live in the URL so a link opens the exact risk/criterion/citation. */
export function useReportNav() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab: TabId = TABS.some((t) => t.id === raw) ? (raw as TabId) : "compliance";
  const focus = params.get("focus");
  const go = useCallback(
    (nextTab: TabId, nextFocus?: string) => {
      const next = new URLSearchParams({ tab: nextTab });
      if (nextFocus) next.set("focus", nextFocus);
      const view = params.get("view");
      if (view) next.set("view", view); // keep the split viewer open across tabs
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
