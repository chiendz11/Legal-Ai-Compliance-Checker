import { useSyncExternalStore } from "react";

/**
 * Two ways to read the app. "simple" is for general users: one conclusion, the points to fix and
 * what to do. "advanced" is the full reviewer view (every requirement, legal basis, review).
 * Both read the same stored results; the simple view only shows less.
 */
export type ViewMode = "simple" | "advanced";

const KEY = "lc.viewMode";
const listeners = new Set<() => void>();

const read = (): ViewMode => (localStorage.getItem(KEY) === "advanced" ? "advanced" : "simple");

export function setViewMode(mode: ViewMode) {
  localStorage.setItem(KEY, mode);
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener); // another tab changed it
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function useViewMode(): ViewMode {
  return useSyncExternalStore(subscribe, read);
}

const MODES: [ViewMode, string, string][] = [
  ["simple", "Đơn giản", "Chỉ kết luận, các điểm cần xem lại và việc nên làm"],
  ["advanced", "Nâng cao", "Đầy đủ từng quy định, căn cứ pháp lý và phần rà soát của chuyên viên"],
];

export function ModeSwitch() {
  const mode = useViewMode();
  return (
    <div className="mode-switch" role="group" aria-label="Chế độ hiển thị">
      {MODES.map(([value, text, hint]) => (
        <button
          key={value}
          type="button"
          aria-pressed={mode === value}
          title={hint}
          onClick={() => setViewMode(value)}
        >
          {text}
        </button>
      ))}
    </div>
  );
}
