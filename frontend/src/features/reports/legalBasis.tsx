import { createContext, useContext } from "react";

import type { LegalBasisItem } from "../../shared/api/client";

/** Legal-basis display records by ID; empty until loaded (chips then fall back to raw IDs). */
export const LegalBasisContext = createContext<Map<string, LegalBasisItem>>(new Map());

function chipText(item: LegalBasisItem): string {
  const number = item.document?.so_hieu;
  switch (item.kind) {
    case "DOCUMENT":
      return [item.number, item.title].filter(Boolean).join(" – ");
    case "ARTICLE":
      return [item.title, number].filter(Boolean).join(", ");
    case "REQUIREMENT_VERSION":
      return `Yêu cầu ${item.id}${number ? ` (${number})` : ""}`;
    default:
      return item.id;
  }
}

function tooltip(item: LegalBasisItem): string {
  return [
    item.id,
    item.kind === "REQUIREMENT_VERSION" || item.kind === "ARTICLE" ? item.title : null,
    item.document?.ten_van_ban,
    item.effective_from && `Hiệu lực từ ${item.effective_from}${item.effective_to ? ` đến ${item.effective_to}` : ""}`,
    item.excerpt,
    item.verification && `Xác minh: ${item.verification}`,
  ]
    .filter(Boolean)
    .join("\n");
}

/** Legal sources still awaiting human review are marked; flags are never upgraded here. */
const unverified = (item: LegalBasisItem) =>
  !!item.verification && /CHUA|PENDING|UNVERIFIED/.test(item.verification);

export function LegalBasis({ ids, empty = "—" }: { ids: string[] | undefined; empty?: string }) {
  const known = useContext(LegalBasisContext);
  if (!ids?.length) return <span className="muted">{empty}</span>;
  return (
    <span className="ids">
      {ids.map((id) => {
        const item = known.get(id);
        if (!item || item.kind === "UNKNOWN") return <code key={id}>{id}</code>;
        const text = chipText(item);
        return (
          <span key={id} className="basis" title={tooltip(item)}>
            {item.url ? (
              <a href={item.url} target="_blank" rel="noreferrer">
                {text}
              </a>
            ) : (
              text
            )}
            {unverified(item) && <span className="tag">chưa duyệt</span>}
          </span>
        );
      })}
    </span>
  );
}
