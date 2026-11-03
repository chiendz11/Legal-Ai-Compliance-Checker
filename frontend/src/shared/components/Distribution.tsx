import { useState, type MouseEvent } from "react";

/**
 * Status colors (dark card surface), checked with the dataviz palette validator: adjacent
 * pairs clear CVD ΔE ≥ 8 and the normal-vision floor ≥ 15; all ≥ 3:1 on the card. Green and
 * red are never adjacent but are close under deuteranopia, so every mark also carries its
 * label (axis, legend, tooltip). Gray is the deliberate "no verdict yet" neutral.
 */
export const STATUS_COLORS = {
  critical: "#d03b3b",
  serious: "#ec835a",
  warning: "#f7d34a",
  good: "#0ca30c",
  none: "#7d8696",
} as const;

export type DistributionItem = { key: string; label: string; count: number; color: string };

type Hover = { key: string; x: number; y: number } | null;

const percent = new Intl.NumberFormat("vi-VN", { style: "percent", maximumFractionDigits: 1 });
const pct = (count: number, total: number) => percent.format(total ? count / total : 0);

/** Column chart + donut + legend table for one categorical breakdown. Counts only, no score. */
export function Distribution({
  title,
  description,
  items,
  unit,
}: {
  title: string;
  description: string;
  items: DistributionItem[];
  unit: string;
}) {
  const [hover, setHover] = useState<Hover>(null);
  const total = items.reduce((sum, item) => sum + item.count, 0);
  const active = items.find((item) => item.key === hover?.key);

  function track(key: string) {
    return {
      onMouseMove: (event: MouseEvent) => {
        const box = (event.currentTarget as Element)
          .closest(".dist")!
          .getBoundingClientRect();
        setHover({ key, x: event.clientX - box.left, y: event.clientY - box.top });
      },
      onMouseLeave: () => setHover(null),
    };
  }

  return (
    <section className="dist" aria-label={title}>
      <header className="dist-head">
        <h3>{title}</h3>
        <p className="muted small">{description}</p>
      </header>
      {total === 0 ? (
        <p className="empty">Không có {unit}.</p>
      ) : (
        <div className="dist-grid">
          <Columns items={items} hover={hover?.key} track={track} />
          <div className="dist-side">
            <Donut items={items} total={total} unit={unit} hover={hover?.key} track={track} />
            <table className="dist-legend">
              <tbody>
                {items.map((item) => (
                  <tr
                    key={item.key}
                    className={hover && hover.key !== item.key ? "dim" : undefined}
                  >
                    <td>
                      <i className="swatch" style={{ background: item.color }} />
                      {item.label}
                    </td>
                    <td className="n">{item.count}</td>
                    <td className="n muted">{pct(item.count, total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {active && hover && (
        <div className="dist-tip" style={{ left: hover.x, top: hover.y }} role="status">
          <b>{active.label}</b>
          {active.count} {unit} · {pct(active.count, total)}
        </div>
      )}
    </section>
  );
}

/**
 * Ticks at 1/2/5 × 10^k so the axis stays at ≤ 5 clean steps, with headroom: when the
 * tallest bar would touch the top tick, add one more step so it never hits the ceiling.
 */
function niceScale(max: number) {
  const raw = Math.max(max, 1) / 4;
  const power = 10 ** Math.floor(Math.log10(raw));
  // Counts are whole numbers: never a fractional step.
  const step = Math.max(1, [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? power);
  let top = Math.ceil(Math.max(max, 1) / step) * step;
  if (top - max < step * 0.25) top += step;
  return { top, ticks: Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step) };
}

type Track = (key: string) => {
  onMouseMove: (event: MouseEvent) => void;
  onMouseLeave: () => void;
};

function Columns({
  items,
  hover,
  track,
}: {
  items: DistributionItem[];
  hover: string | undefined;
  track: Track;
}) {
  const { top, ticks } = niceScale(Math.max(...items.map((item) => item.count)));
  return (
    <div className="dist-cols">
      <div className="dist-plot">
        {ticks.map((tick) => (
          <div key={tick} className="gridline" style={{ bottom: `${(tick / top) * 100}%` }}>
            <span>{tick}</span>
          </div>
        ))}
        <div className="dist-bars">
          {items.map((item) => (
            <div
              key={item.key}
              className={`dist-col${hover && hover !== item.key ? " dim" : ""}`}
              {...track(item.key)}
            >
              {item.count > 0 && (
                <div className="dist-bar" style={{ height: `${(item.count / top) * 100}%` }}>
                  <span className="dist-val">{item.count}</span>
                  <i style={{ background: item.color }} />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="dist-xlabels">
        {items.map((item) => (
          <span key={item.key}>{item.label}</span>
        ))}
      </div>
    </div>
  );
}

const R = 70;
const C = 2 * Math.PI * R;
const GAP = 2; // surface gap between segments, in px of arc

function Donut({
  items,
  total,
  unit,
  hover,
  track,
}: {
  items: DistributionItem[];
  total: number;
  unit: string;
  hover: string | undefined;
  track: Track;
}) {
  const parts = items.filter((item) => item.count > 0);
  const gap = parts.length > 1 ? GAP : 0;
  let offset = 0;
  return (
    <svg className="dist-donut" viewBox="0 0 200 200" role="img" aria-label={`${total} ${unit}`}>
      <g transform="rotate(-90 100 100)">
        {parts.map((item) => {
          const length = (item.count / total) * C;
          const dash = Math.max(length - gap, 0.5);
          const segment = (
            <circle
              key={item.key}
              cx="100"
              cy="100"
              r={R}
              fill="none"
              stroke={item.color}
              strokeWidth={hover === item.key ? 30 : 26}
              strokeDasharray={`${dash} ${C - dash}`}
              strokeDashoffset={-offset}
              opacity={hover && hover !== item.key ? 0.35 : 1}
              {...track(item.key)}
            />
          );
          offset += length;
          return segment;
        })}
      </g>
      <text x="100" y="98" textAnchor="middle" className="dist-total">
        {total}
      </text>
      <text x="100" y="120" textAnchor="middle" className="dist-unit">
        {unit}
      </text>
    </svg>
  );
}
