import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

export const TABS = [
  { id: "profile", title: "Hồ sơ hợp đồng" },
  { id: "scope", title: "Phạm vi pháp lý" },
  { id: "compliance", title: "Tuân thủ" },
  { id: "citations", title: "Viện dẫn" },
  { id: "risks", title: "Rủi ro" },
  { id: "recommendations", title: "Khuyến nghị" },
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
      setParams(next);
    },
    [setParams],
  );
  return { tab, focus, go };
}

export const focusDomId = (id: string) => `focus-${id}`;
