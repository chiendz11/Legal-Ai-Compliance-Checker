import type { ReactNode } from "react";

import { label, type LabelKind } from "../labels";
import { displayText } from "../text";

export function StatusBadge({ kind, code }: { kind: LabelKind; code: string | null | undefined }) {
  const { text, tone } = label(kind, code);
  return (
    <span className={`badge tone-${tone}`} title={code ?? undefined}>
      {text}
    </span>
  );
}

export function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="section">
      <header className="section-head">
        <h2>{title}</h2>
        {description && <p className="muted">{description}</p>}
      </header>
      {children}
    </section>
  );
}

/** Scrolls horizontally inside its own box so wide tables never widen the page on phones. */
export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="table-wrap">
      <table className="table">{children}</table>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

export function Notice({ tone, children }: { tone: "warn" | "info" | "bad"; children: ReactNode }) {
  return (
    <div className={`notice tone-${tone}`} role="note">
      {children}
    </div>
  );
}

/** Field list that shows null explicitly; unknown facts must stay visible as unknown. */
export function Fields({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="fields">
      {rows.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{value ?? <span className="null">chưa có</span>}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Value({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="null">chưa có</span>;
  if (typeof value === "boolean") return <>{value ? "Có" : "Không"}</>;
  if (typeof value === "object") return <code>{JSON.stringify(value)}</code>;
  return <>{displayText(String(value))}</>;
}

export function Ids({ ids, empty = "—" }: { ids: string[] | undefined; empty?: string }) {
  if (!ids?.length) return <span className="muted">{empty}</span>;
  return (
    <span className="ids">
      {ids.map((id) => (
        <code key={id}>{id}</code>
      ))}
    </span>
  );
}

/** Contract quote with its chunk and character span, so a reviewer can trace it to the source. */
export function Quote({
  text,
  chunkId,
  start,
  end,
  pages,
}: {
  text: string;
  chunkId: string;
  start?: number;
  end?: number;
  pages?: string;
}) {
  return (
    <figure className="quote">
      <blockquote>{displayText(text)}</blockquote>
      <figcaption>
        <code>{chunkId}</code>
        {start !== undefined && end !== undefined && (
          <span>
            ký tự {start}–{end}
          </span>
        )}
        {pages && <span>{pages}</span>}
      </figcaption>
    </figure>
  );
}

export function Disclosure({ summary, children }: { summary: ReactNode; children: ReactNode }) {
  return (
    <details className="disclosure">
      <summary>{summary}</summary>
      <div className="disclosure-body">{children}</div>
    </details>
  );
}

export function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}

export function LoadState({ error, children }: { error: unknown; children?: ReactNode }) {
  if (error) {
    const status = (error as { status?: number }).status;
    return (
      <Notice tone="bad">
        Không tải được dữ liệu{status ? ` (HTTP ${status})` : ""}. Route này có thể chưa được
        backend triển khai; bật mock bằng <code>VITE_API_MOCK=true</code>.
      </Notice>
    );
  }
  return <p className="muted">{children ?? "Đang tải…"}</p>;
}
