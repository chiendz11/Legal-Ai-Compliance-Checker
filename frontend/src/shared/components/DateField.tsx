import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { Icon } from "./icons";

/** Vietnamese date picker. Value is "YYYY-MM-DD" or "" (unknown), like <input type="date">. */
type Day = { y: number; m: number; d: number }; // m is 0-based

const WEEKDAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];
const pad = (n: number) => String(n).padStart(2, "0");
const iso = ({ y, m, d }: Day) => `${y}-${pad(m + 1)}-${pad(d)}`;
const shown = ({ y, m, d }: Day) => `${pad(d)}/${pad(m + 1)}/${y}`;
const fromDate = (date: Date): Day => ({
  y: date.getFullYear(),
  m: date.getMonth(),
  d: date.getDate(),
});
const shift = (day: Day, days: number) => fromDate(new Date(day.y, day.m, day.d + days));

function parse(value: string): Day | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const [, y, m, d] = match.map(Number);
  return { y: y!, m: m! - 1, d: d! };
}

/** 6 weeks starting on the Monday on or before the 1st of the month. */
function monthGrid(y: number, m: number): Day[] {
  const first = new Date(y, m, 1);
  const lead = (first.getDay() + 6) % 7;
  return Array.from({ length: 42 }, (_, i) => fromDate(new Date(y, m, 1 - lead + i)));
}

export function DateField({
  value,
  onChange,
  disabled,
  clearable = true,
  placeholder = "dd/mm/yyyy",
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  clearable?: boolean;
  placeholder?: string;
}) {
  const selected = parse(value);
  const today = fromDate(new Date());
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState<Day>(selected ?? today);
  const root = useRef<HTMLDivElement>(null);
  const grid = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  // Keep keyboard focus on the cursor day while the calendar is open.
  useEffect(() => {
    if (open) grid.current?.querySelector<HTMLElement>(`[data-day="${iso(cursor)}"]`)?.focus();
  }, [open, cursor]);

  function toggle() {
    if (!open) setCursor(selected ?? today);
    setOpen(!open);
  }

  function pick(day: Day | null) {
    onChange(day ? iso(day) : "");
    setOpen(false);
  }

  function onGridKey(event: KeyboardEvent) {
    const moves: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
    const move = moves[event.key];
    if (move !== undefined) {
      event.preventDefault();
      setCursor(shift(cursor, move));
    } else if (event.key === "PageUp" || event.key === "PageDown") {
      event.preventDefault();
      const step = event.key === "PageUp" ? -1 : 1;
      setCursor(fromDate(new Date(cursor.y, cursor.m + step, Math.min(cursor.d, 28))));
    }
  }

  const days = monthGrid(cursor.y, cursor.m);
  const same = (a: Day | null, b: Day) => !!a && a.y === b.y && a.m === b.m && a.d === b.d;

  return (
    <div
      className="datefield"
      ref={root}
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.stopPropagation();
          setOpen(false);
        }
      }}
    >
      <button
        type="button"
        className="date-trigger"
        disabled={disabled}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={toggle}
      >
        <span className={selected ? undefined : "muted"}>
          {selected ? shown(selected) : placeholder}
        </span>
        <Icon name="calendar" />
      </button>
      {open && (
        // Inside a <label>: cancel the label's click so it does not re-toggle the trigger.
        <div
          className="date-pop"
          role="dialog"
          aria-label="Chọn ngày"
          onClick={(event) => event.preventDefault()}
        >
          <div className="date-head">
            <button
              type="button"
              className="date-nav"
              aria-label="Tháng trước"
              onClick={() => setCursor(fromDate(new Date(cursor.y, cursor.m - 1, 1)))}
            >
              <Icon name="chevronLeft" />
            </button>
            <strong>
              Tháng {cursor.m + 1}, {cursor.y}
            </strong>
            <button
              type="button"
              className="date-nav"
              aria-label="Tháng sau"
              onClick={() => setCursor(fromDate(new Date(cursor.y, cursor.m + 1, 1)))}
            >
              <Icon name="chevronRight" />
            </button>
          </div>
          <div className="date-grid" role="grid" ref={grid} onKeyDown={onGridKey}>
            {WEEKDAYS.map((w) => (
              <span key={w} className="date-wd" role="columnheader">
                {w}
              </span>
            ))}
            {days.map((day) => {
              const classes = [
                "date-day",
                day.m !== cursor.m && "out",
                same(today, day) && "today",
                same(selected, day) && "on",
              ].filter(Boolean);
              return (
                <button
                  key={iso(day)}
                  type="button"
                  role="gridcell"
                  data-day={iso(day)}
                  className={classes.join(" ")}
                  tabIndex={same(cursor, day) ? 0 : -1}
                  aria-selected={same(selected, day)}
                  aria-label={shown(day)}
                  onClick={() => pick(day)}
                >
                  {day.d}
                </button>
              );
            })}
          </div>
          <div className="date-foot">
            {clearable ? (
              <button type="button" className="button ghost" onClick={() => pick(null)}>
                Xóa
              </button>
            ) : (
              <span />
            )}
            <button type="button" className="button ghost" onClick={() => pick(today)}>
              Hôm nay
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
