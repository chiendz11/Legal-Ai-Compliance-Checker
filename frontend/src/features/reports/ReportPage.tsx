import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { AssessmentCase, ReportRecord } from "../../shared/api/client";
import { useCases, useLegalBasis, useReport, useRequirementNames } from "../../shared/api/queries";
import { Icon } from "../../shared/components/icons";
import { LoadState, MachineText, Notice } from "../../shared/components/ui";
import { mockEnabled } from "../../shared/env";
import { CitationsSection } from "../assessments/citations/CitationsSection";
import { TopicsSection } from "../assessments/compliance/ComplianceSection";
import { contractSourceUrl, EvidenceProvider } from "../assessments/evidence/EvidenceViewer";
import { PdfViewer, type PdfTarget } from "../assessments/evidence/PdfViewer";
import { ProfileSection } from "../assessments/profile/ProfileSection";
import { ReviewWorkbench } from "../review/ReviewWorkbench";
import { viDate } from "./explain";
import { LegalBasisContext } from "./legalBasis";
import { focusDomId, TABS, type TabId, useReportNav } from "./nav";
import { OverviewSection } from "./OverviewSection";
import {
  buildIndex,
  ReportIndexContext,
  type RequirementInfo,
  RequirementNamesContext,
} from "./reportIndex";
import { TechnicalSection } from "./TechnicalSection";
import { ReportPresentationContext } from "./assessmentStatus";

export function ReportPage() {
  const { baoCaoId = "" } = useParams();
  const { data, error } = useReport(baoCaoId);
  if (!data) return <LoadState error={error} />;
  return <ReportView record={data} />;
}

function ReportView({ record }: { record: ReportRecord }) {
  const report = record.report;
  const content = report.report_json;
  const index = useMemo(() => buildIndex(content), [content]);
  const legalBasis = useLegalBasis(report.bao_cao_id);
  const basisById = useMemo(
    () => new Map((legalBasis.data?.items ?? []).map((item) => [item.id, item])),
    [legalBasis.data],
  );
  const requirementNames = useRequirementNames(report.bao_cao_id);
  const namesById = useMemo(
    () =>
      new Map<string, RequirementInfo>(
        (requirementNames.data?.items ?? []).map((item) => [
          item.requirement_id,
          { title: item.title, group: item.obligation_group ?? null },
        ]),
      ),
    [requirementNames.data],
  );
  const { tab, focus, split, setSplit } = useReportNav();
  const [pdfPage, setPdfPage] = useState(1);
  const [pdfTarget, setPdfTarget] = useState<PdfTarget | null>(null);
  const source = useContractSource(content.case);
  // Evidence clicks open the original PDF beside the report and highlight the quote there;
  // without a readable PDF they fall back to the text drawer.
  const pdfMode = content.case.source.mime_type === "application/pdf" && !source.error;
  // Opening the PDF narrows the report column and reflows it; keep the clicked button where
  // the reader saw it instead of letting the page jump.
  const anchor = useRef<{ el: HTMLElement; top: number } | null>(null);
  const locate = useCallback(
    (target: Omit<PdfTarget, "nonce">) => {
      setPdfTarget({ ...target, nonce: Date.now() });
      if (!split) {
        const el = document.activeElement;
        anchor.current =
          el instanceof HTMLElement && el !== document.body
            ? { el, top: el.getBoundingClientRect().top }
            : null;
        setSplit(true);
      }
    },
    [split, setSplit],
  );
  useLayoutEffect(() => {
    const kept = anchor.current;
    anchor.current = null;
    if (kept?.el.isConnected) window.scrollBy(0, kept.el.getBoundingClientRect().top - kept.top);
  }, [split]);

  useEffect(() => {
    if (!focus) return;
    // Let the target section (and any auto-opened <details>) render first. A timer, not
    // requestAnimationFrame, which never fires while the tab is in the background.
    const timer = setTimeout(
      () => document.getElementById(focusDomId(focus))?.scrollIntoView({ block: "center" }),
      50,
    );
    return () => clearTimeout(timer);
    // Topic groups and legal-basis text load later and move the target; scroll again then.
  }, [tab, focus, namesById, basisById]);

  return (
    <ReportPresentationContext.Provider value={record.presentation ?? null}>
    <ReportIndexContext.Provider value={index}>
      <RequirementNamesContext.Provider value={namesById}>
        <LegalBasisContext.Provider value={basisById}>
          <EvidenceProvider
            caseInfo={content.case}
            runId={record.run_id}
            onLocate={pdfMode ? locate : undefined}
          >
            {/* One tree for both layouts: toggling the PDF must not remount the report, which
                would close every opened topic and lose the reader's place. */}
            <div className={split ? "split-layout" : undefined}>
              {split && (
                <SourcePane
                  caseInfo={content.case}
                  source={source}
                  page={pdfPage}
                  target={pdfTarget}
                  onPage={setPdfPage}
                />
              )}
              <div className={split ? "split-report" : undefined}>
                <ReportBody record={record} />
              </div>
            </div>
          </EvidenceProvider>
        </LegalBasisContext.Provider>
      </RequirementNamesContext.Provider>
    </ReportIndexContext.Provider>
    </ReportPresentationContext.Provider>
  );
}

/** The original PDF as a same-origin blob URL (checks tenant access; one download per page). */
function useContractSource(caseInfo: AssessmentCase) {
  const url = contractSourceUrl(caseInfo.hop_dong_id);
  const source = useQuery({
    queryKey: ["contract-source", caseInfo.hop_dong_id],
    enabled: caseInfo.source.mime_type === "application/pdf",
    staleTime: Infinity,
    retry: false,
    queryFn: async () => {
      const response = await fetch(url);
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message ?? `HTTP ${response.status}`);
      }
      return URL.createObjectURL(await response.blob());
    },
  });
  return source;
}

/** Original contract beside the findings; evidence clicks highlight the quote in it. */
function SourcePane({
  caseInfo,
  source,
  page,
  target,
  onPage,
}: {
  caseInfo: AssessmentCase;
  source: ReturnType<typeof useContractSource>;
  page: number;
  target: PdfTarget | null;
  onPage: (page: number) => void;
}) {
  const pdf = caseInfo.source.mime_type === "application/pdf";
  const url = contractSourceUrl(caseInfo.hop_dong_id);
  return (
    <aside className="pdf-pane" aria-label="Hợp đồng gốc">
      <div className="pdf-pane-head small">
        <span>
          Hợp đồng gốc · trang {page} · SHA-256 <code>{caseInfo.source.sha256.slice(0, 12)}…</code>
        </span>
        {!source.error && (
          <a href={`${url}#page=${page}`} target="_blank" rel="noreferrer">
            Mở tab mới
          </a>
        )}
      </div>
      {pdf ? (
        source.data ? (
          <PdfViewer url={source.data} target={target} onPage={onPage} />
        ) : source.error ? (
          <Notice tone="warn">
            <strong>Chưa xem được tệp gốc ở đây.</strong> Tệp PDF của ca này nằm trên máy chủ lưu
            trữ của dataset, hiện không truy cập được. Báo cáo, trích dẫn và vị trí trang vẫn dùng
            bình thường; hợp đồng tải lên hệ thống thì xem được trực tiếp.
            {caseInfo.source.url_nguon && (
              <div className="actions">
                <a
                  className="button"
                  href={caseInfo.source.url_nguon}
                  target="_blank"
                  rel="noreferrer"
                >
                  Mở bản công khai tại nguồn
                </a>
                <span className="small muted">
                  Có thể khác bản đã băm SHA-256 trong báo cáo.
                </span>
              </div>
            )}
            <MachineText text={source.error.message} />
          </Notice>
        ) : (
          <p className="muted small">Đang tải tệp gốc…</p>
        )
      ) : (
        <p className="muted small">
          Tệp DOCX không xem trực tiếp được trong trình duyệt. <a href={url}>Tải tệp gốc</a>.
        </p>
      )}
    </aside>
  );
}

function ReportBody({ record }: { record: ReportRecord }) {
  const report = record.report;
  const content = report.report_json;
  const { tab } = useReportNav();
  return (
    <>
      <ReportHeader record={record} />
      {mockEnabled && (
        <Notice tone="info">
          Dữ liệu mẫu (mock): báo cáo tham chiếu dùng để dựng giao diện, không phải kết quả chạy thật.
        </Notice>
      )}
      <div className="report-layout">
        <SectionNav record={record} />
        <div className="report-content">
          {tab === "overview" && <OverviewSection report={report} />}
          {tab === "topics" && <TopicsSection content={content} />}
          {tab === "contract" && (
            <>
              <ProfileSection profile={content.contract_profile} />
              <CitationsSection citations={content.citation_validation} />
            </>
          )}
          {tab === "review" &&
            (mockEnabled ? (
              <Notice tone="info">Rà soát cần máy chủ thật; chế độ dữ liệu mẫu chỉ đọc.</Notice>
            ) : (
              <ReviewWorkbench record={record} />
            ))}
          {tab === "technical" && <TechnicalSection record={record} />}
        </div>
      </div>
    </>
  );
}

/** Document name from the case list; the report itself only stores IDs. */
function useDocumentName(caId: string, fallback: string) {
  const { data } = useCases({ q: caId, page_size: 1 });
  const item = data?.items.find((i) => i.case.ca_id === caId);
  return item?.ten_tai_lieu ?? fallback;
}

function ReportHeader({ record }: { record: ReportRecord }) {
  const { report } = record;
  const kase = report.report_json.case;
  const name = useDocumentName(kase.ca_id, `Hợp đồng ${kase.hop_dong_id}`);
  const published = report.report_status === "PUBLISHED";
  return (
    <header className="report-header">
      <p className="crumbs">
        <Link to="/">Hợp đồng</Link> / Báo cáo
      </p>
      <h1>{name}</h1>
      <div className="header-meta">
        <span className={`badge tone-${published ? "good" : "warn"}`}>
          {published ? "Đã phát hành" : "Bản nháp · chưa duyệt"}
        </span>
        {kase.assessment_context.review_mode === "DRAFT_REVIEW" && (
          <span className="badge tone-neutral">Rà soát dự thảo trước khi ký</span>
        )}
        <span>Đánh giá ngày {viDate(kase.assessment_context.ngay_danh_gia)}</span>
        <Link to="/help#doc-bao-cao" className="small">
          Cách đọc báo cáo này
        </Link>
      </div>
      {!mockEnabled && (
        <div className="actions">
          <SplitToggle />
          <details className="menu">
            <summary className="button">
              <Icon name="download" />
              Tải báo cáo
            </summary>
            <div className="menu-list">
              {(
                [
                  ["pdf", "PDF – để đọc, in"],
                  ["docx", "Word (DOCX) – để chỉnh sửa"],
                  ["json", "JSON – dữ liệu gốc có dấu xác thực"],
                ] as const
              ).map(([format, text]) => (
                <a
                  key={format}
                  href={`/api/v1/reports/${encodeURIComponent(report.bao_cao_id)}/export?format=${format}`}
                >
                  {text}
                </a>
              ))}
            </div>
          </details>
        </div>
      )}
    </header>
  );
}

function SplitToggle() {
  const { split, setSplit } = useReportNav();
  return (
    <button type="button" className="button" aria-pressed={split} onClick={() => setSplit(!split)}>
      {split ? "Đóng hợp đồng gốc" : "Xem cùng hợp đồng gốc"}
    </button>
  );
}

/** Left table of contents: four reading steps, then engineering detail apart. */
function SectionNav({ record }: { record: ReportRecord }) {
  const { tab, go } = useReportNav();
  const content = record.report.report_json;
  const results = content.compliance.requirement_results;
  const attention =
    results.filter((r) => r.status === "NON_COMPLIANT" || r.status === "PARTIAL").length +
    content.risks.compliance.length +
    content.risks.citation.length;
  const counts: Partial<Record<TabId, number>> = { topics: results.length };
  const steps = TABS.filter((t) => t.id !== "technical");
  return (
    <nav className="section-nav" aria-label="Mục lục báo cáo">
      {steps.map((t, i) => (
        <button
          key={t.id}
          type="button"
          className={t.id === tab ? "active" : undefined}
          aria-current={t.id === tab ? "page" : undefined}
          onClick={() => go(t.id)}
        >
          <span className="section-num">{i + 1}</span>
          <span className="section-title">{t.title}</span>
          {t.id === "overview" && attention > 0 && (
            <span className="section-count hot" title="Điểm cần chú ý">
              {attention}
            </span>
          )}
          {counts[t.id] !== undefined && <span className="section-count">{counts[t.id]}</span>}
        </button>
      ))}
      <button
        type="button"
        className={`muted-item${tab === "technical" ? " active" : ""}`}
        aria-current={tab === "technical" ? "page" : undefined}
        onClick={() => go("technical")}
      >
        <span className="section-title">Chi tiết kỹ thuật (cho kỹ sư)</span>
      </button>
    </nav>
  );
}
