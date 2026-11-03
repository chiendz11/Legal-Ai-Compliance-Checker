import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { AssessmentCase, FinalReport, ReportRecord } from "../../shared/api/client";
import { useLegalBasis, useReport } from "../../shared/api/queries";
import { LoadState, MachineText, Notice, StatusBadge } from "../../shared/components/ui";
import { mockEnabled } from "../../shared/env";
import { label } from "../../shared/labels";
import { CitationsSection } from "../assessments/citations/CitationsSection";
import { ChecklistSection } from "../assessments/checklist/ChecklistSection";
import { ComplianceSection } from "../assessments/compliance/ComplianceSection";
import { contractSourceUrl, EvidenceProvider } from "../assessments/evidence/EvidenceViewer";
import { ProfileSection } from "../assessments/profile/ProfileSection";
import { RecommendationsSection } from "../assessments/recommendations/RecommendationsSection";
import { RisksSection } from "../assessments/risks/RisksSection";
import { ReviewWorkbench } from "../review/ReviewWorkbench";
import { AuditSection } from "./AuditSection";
import { LegalBasisContext } from "./legalBasis";
import { focusDomId, TABS, useReportNav } from "./nav";
import { buildIndex, ReportIndexContext } from "./reportIndex";
import { SummaryTiles } from "./SummaryTiles";

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
  const { tab, focus, split } = useReportNav();
  const [pdfPage, setPdfPage] = useState(1);

  useEffect(() => {
    if (!focus) return;
    // Wait a frame so the target tab (and any auto-opened <details>) has rendered.
    const frame = requestAnimationFrame(() =>
      document.getElementById(focusDomId(focus))?.scrollIntoView({ block: "center" }),
    );
    return () => cancelAnimationFrame(frame);
  }, [tab, focus]);

  return (
    <ReportIndexContext.Provider value={index}>
      <LegalBasisContext.Provider value={basisById}>
        <EvidenceProvider
          caseInfo={content.case}
          runId={record.run_id}
          onLocate={split ? setPdfPage : undefined}
        >
          {split ? (
            <div className="split-layout">
              <SourcePane caseInfo={content.case} page={pdfPage} />
              <div className="split-report">
                <ReportBody record={record} />
              </div>
            </div>
          ) : (
            <ReportBody record={record} />
          )}
        </EvidenceProvider>
      </LegalBasisContext.Provider>
    </ReportIndexContext.Provider>
  );
}

/** Original contract beside the findings; evidence clicks move it to the cited page. */
function SourcePane({ caseInfo, page }: { caseInfo: AssessmentCase; page: number }) {
  const pdf = caseInfo.source.mime_type === "application/pdf";
  const url = contractSourceUrl(caseInfo.hop_dong_id);
  // Fetch once as a blob: page jumps are instant and a missing source shows a clear error.
  const source = useQuery({
    queryKey: ["contract-source", caseInfo.hop_dong_id],
    enabled: pdf,
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
  useEffect(() => {
    const objectUrl = source.data;
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [source.data]);
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
          // Re-keyed per page so the browser PDF viewer opens at the cited page.
          <iframe key={page} title="Hợp đồng gốc" src={`${source.data}#page=${page}`} />
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
      <ReportBanners report={report} />
      <SummaryTiles content={content} />
      <TabBar />
      <div className="tab-panel">
        {tab === "profile" && <ProfileSection profile={content.contract_profile} />}
        {tab === "scope" && (
          <ChecklistSection
            applicable={content.applicable_legal_scope}
            checklist={content.checklist}
          />
        )}
        {tab === "compliance" && <ComplianceSection content={content} />}
        {tab === "citations" && <CitationsSection citations={content.citation_validation} />}
        {tab === "risks" && (
          <RisksSection risks={content.risks} recommendations={content.recommendations} />
        )}
        {tab === "recommendations" && (
          <RecommendationsSection recommendations={content.recommendations} />
        )}
        {tab === "review" &&
          (mockEnabled ? (
            <Notice tone="info">Rà soát cần backend thật; chế độ mock chỉ đọc.</Notice>
          ) : (
            <ReviewWorkbench record={record} />
          ))}
        {tab === "audit" && <AuditSection record={record} />}
      </div>
    </>
  );
}

function ReportHeader({ record }: { record: ReportRecord }) {
  const { report } = record;
  const kase = report.report_json.case;
  return (
    <header className="report-header">
      <p className="crumbs">
        <Link to="/">Lịch sử</Link> / {kase.ca_id}
      </p>
      <h1>Báo cáo đánh giá hợp đồng {kase.hop_dong_id}</h1>
      <div className="header-meta">
        <StatusBadge kind="reportStatus" code={report.report_status} />
        <StatusBadge kind="review" code={report.review_status} />
        <span>
          Phiên bản <code>{report.phien_ban_bao_cao}</code>
        </span>
        <span>
          Run <code>{record.run_id}</code>
        </span>
        <span>Ngày đánh giá {kase.assessment_context.ngay_danh_gia}</span>
        <span>
          Mốc áp dụng {kase.assessment_context.moc_ap_dung ?? "chưa rõ"} (
          {kase.assessment_context.loai_moc_ap_dung
            ? label("anchor", kase.assessment_context.loai_moc_ap_dung).text
            : "chưa rõ loại mốc"}
          )
        </span>
      </div>
      {!mockEnabled && (
        <div className="actions">
          <SplitToggle />
          {(["pdf", "docx", "json"] as const).map((format) => (
            <a
              key={format}
              className="button"
              href={`/api/v1/reports/${encodeURIComponent(report.bao_cao_id)}/export?format=${format}`}
            >
              Tải {format.toUpperCase()}
            </a>
          ))}
        </div>
      )}
    </header>
  );
}

function ReportBanners({ report }: { report: FinalReport }) {
  return (
    <>
      {report.report_status === "PUBLISHED" ? (
        <Notice tone="info">
          <strong>Đã phát hành.</strong> Các mục chuyên viên chỉnh sửa nằm ở tab Rà soát và phần
          audit.review; kết quả máy trong các tab khác được giữ nguyên để đối chiếu.
        </Notice>
      ) : (
        <Notice tone="warn">
          <strong>Kết quả máy, chưa được phát hành.</strong> Báo cáo đang ở trạng thái “
          {label("reportStatus", report.report_status).text} /{" "}
          {label("review", report.review_status).text}
          ”; không dùng như kết luận pháp lý đã duyệt.
        </Notice>
      )}
      {mockEnabled && (
        <Notice tone="info">
          Dữ liệu mock: report tham chiếu QA (EXPECTED) dùng để dựng giao diện, không phải output
          của một lần chạy dev.
        </Notice>
      )}
      {report.report_json.audit.module_source === "MODULES_DI_REFERENCE" && (
        <Notice tone="info">
          <strong>Module thật (bước 3–7):</strong> phạm vi, phiên bản, viện dẫn, truy xuất, tuân
          thủ, rủi ro và khuyến nghị do các module của nhóm B/C tính. Riêng hồ sơ hợp đồng và đoạn
          văn (bước 1–2) lấy từ dataset tham chiếu vì module đọc hợp đồng (nhóm A) chưa gộp.
        </Notice>
      )}
      {report.report_json.audit.module_source === "REFERENCE_REPLAY" && (
        <Notice tone="info">
          <strong>REFERENCE_REPLAY:</strong> run này phát lại dữ liệu tham chiếu QA qua luồng điều
          phối thật để kiểm thử tích hợp; đây không phải kết quả của các module đánh giá.
        </Notice>
      )}
    </>
  );
}

function SplitToggle() {
  const { split, setSplit } = useReportNav();
  return (
    <button type="button" className="button" aria-pressed={split} onClick={() => setSplit(!split)}>
      {split ? "Đóng xem song song" : "Xem song song với hợp đồng"}
    </button>
  );
}

function TabBar() {
  const { tab, go } = useReportNav();
  return (
    <nav className="tabs" aria-label="Các phần báo cáo">
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={t.id === tab ? "active" : undefined}
          aria-current={t.id === tab ? "page" : undefined}
          onClick={() => go(t.id)}
        >
          {t.title}
        </button>
      ))}
    </nav>
  );
}
