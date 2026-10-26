import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import type { AssessmentCase } from "../../../shared/api/client";
import { useRunResults } from "../../../shared/api/queries";
import { Notice } from "../../../shared/components/ui";
import { displayText } from "../../../shared/text";

/** A span inside one contract chunk; offsets are absent for page-level citation positions. */
export type EvidenceTarget = { doanId: string; start?: number; end?: number; quote?: string };

const EvidenceContext = createContext<((target: EvidenceTarget) => void) | null>(null);

/** Opens the viewer when inside a report; null elsewhere so callers can hide the button. */
export function useOpenEvidence() {
  return useContext(EvidenceContext);
}

/**
 * Resolves C06/C07/C02 evidence to the exact chunk of the run's pinned document, with the
 * quoted span highlighted, its pages, and a link to the source PDF at that page.
 */
export function EvidenceProvider({
  caseInfo,
  runId,
  children,
}: {
  caseInfo: AssessmentCase;
  runId: string;
  children: ReactNode;
}) {
  const [target, setTarget] = useState<EvidenceTarget | null>(null);
  const [opened, setOpened] = useState(false);
  const results = useRunResults(caseInfo.ca_id, runId, opened);

  const open = (next: EvidenceTarget) => {
    setOpened(true);
    setTarget(next);
  };

  useEffect(() => {
    if (!target) return;
    const close = (event: KeyboardEvent) => event.key === "Escape" && setTarget(null);
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [target]);

  const chunk = results.data?.chunks.find((c) => c.doan_id === target?.doanId);
  const source = caseInfo.source.object_uri ?? caseInfo.source.url_nguon;
  const pdfLink =
    chunk && source && /^https?:/.test(source) && caseInfo.source.mime_type === "application/pdf"
      ? `${source}#page=${chunk.page_start}`
      : null;

  return (
    <EvidenceContext.Provider value={open}>
      {children}
      {target && (
        <aside className="drawer" role="dialog" aria-label="Bằng chứng trong hợp đồng">
          <header className="drawer-head">
            <strong>Đoạn hợp đồng</strong>
            <code>{target.doanId}</code>
            <button type="button" className="button" onClick={() => setTarget(null)}>
              Đóng
            </button>
          </header>
          {results.isPending && <p className="muted">Đang tải văn bản của run…</p>}
          {results.error && (
            <Notice tone="bad">
              Không tải được văn bản đã pin của run (cần backend; chế độ mock không có).
            </Notice>
          )}
          {results.data && !chunk && (
            <Notice tone="bad">Đoạn {target.doanId} không có trong tài liệu của run này.</Notice>
          )}
          {chunk && (
            <>
              <p className="small muted">
                Trang {chunk.page_start}
                {chunk.page_end !== chunk.page_start && `–${chunk.page_end}`}
                {target.start !== undefined && ` · ký tự ${target.start}–${target.end}`}
                {pdfLink && (
                  <>
                    {" · "}
                    <a href={pdfLink} target="_blank" rel="noreferrer">
                      Mở PDF gốc tại trang {chunk.page_start}
                    </a>
                  </>
                )}
              </p>
              <ChunkText text={chunk.noi_dung} target={target} />
            </>
          )}
        </aside>
      )}
    </EvidenceContext.Provider>
  );
}

function ChunkText({ text, target }: { text: string; target: EvidenceTarget }) {
  const { start, end, quote } = target;
  const span = start !== undefined && end !== undefined ? text.slice(start, end) : null;
  // A quote that no longer matches its offsets is a provenance error, shown rather than hidden.
  const mismatch = span !== null && quote !== undefined && span !== quote;
  return (
    <>
      {mismatch && (
        <Notice tone="bad">Trích dẫn không khớp vị trí ký tự trong đoạn; cần kiểm tra lại.</Notice>
      )}
      <pre className="chunk">
        {span === null ? (
          displayText(text)
        ) : (
          <>
            {displayText(text.slice(0, start))}
            <mark ref={(el) => el?.scrollIntoView({ block: "center" })}>{displayText(span)}</mark>
            {displayText(text.slice(end))}
          </>
        )}
      </pre>
    </>
  );
}
