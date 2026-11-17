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
      // The requirement itself is already the card title; name the law it comes from.
      return item.document
        ? [number, item.document.ten_van_ban].filter(Boolean).join(" – ")
        : "Quy định trong kho tri thức";
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

/**
 * vbpl.vn moved to a new site. Old document pages (".../Pages/vbpq-thuoctinh.aspx?ItemID=N",
 * "vbpq-toanvan.aspx") open the same document at "/van-ban/chi-tiet/van-ban--N"; the API does
 * this for legal-basis items and this mirrors it for links read straight from the report.
 * Other retired vbpl.vn pages (e.g. "related documents", which names another document) have
 * no safe equivalent and become a search for the document number and name.
 */
const OLD_VBPL_DOC =
  /^https?:\/\/(?:www\.)?vbpl\.vn\/.+\/Pages\/vbpq-(?:thuoctinh|toanvan)\.aspx\?(?:.*&)?ItemID=(\d+)/i;
const DEAD_SOURCE = /vbpl\.vn\/.+\/Pages\//i;

export function legalSourceUrl(url: string | null | undefined, query: string): string | null {
  const moved = url?.match(OLD_VBPL_DOC);
  if (moved) return `https://vbpl.vn/van-ban/chi-tiet/van-ban--${moved[1]}`;
  if (url && !DEAD_SOURCE.test(url)) return url;
  const text = query.trim();
  return text ? `https://www.google.com/search?q=${encodeURIComponent(text)}` : null;
}

function searchText(item: LegalBasisItem): string {
  const number = item.document?.so_hieu ?? item.number;
  const name = item.document?.ten_van_ban ?? (item.kind === "DOCUMENT" ? item.title : null);
  return [number && `"${number}"`, name].filter(Boolean).join(" ");
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
        if (!item || item.kind === "UNKNOWN")
          return (
            <span key={id} className="basis muted" title={id}>
              {known.size ? "văn bản chưa có trong kho tri thức" : "đang tải…"}
            </span>
          );
        const text = chipText(item);
        const href = legalSourceUrl(item.url, searchText(item));
        return (
          <span key={id} className="basis" title={tooltip(item)}>
            {href ? (
              <a href={href} target="_blank" rel="noreferrer">
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
