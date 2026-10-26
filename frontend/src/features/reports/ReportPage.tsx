import { useEffect, useMemo } from "react";
import { Link, useParams } from "react-router-dom";

import type { FinalReport, ReportRecord } from "../../shared/api/client";
import { useLegalBasis, useReport } from "../../shared/api/queries";
import { LoadState, Notice, StatusBadge } from "../../shared/components/ui";
import { mockEnabled } from "../../shared/env";
import { CitationsSection } from "../assessments/citations/CitationsSection";
import { ChecklistSection } from "../assessments/checklist/ChecklistSection";
import { ComplianceSection } from "../assessments/compliance/ComplianceSection";
import { EvidenceProvider } from "../assessments/evidence/EvidenceViewer";
import { ProfileSection } from "../assessments/profile/ProfileSection";
import { RecommendationsSection } from "../assessments/recommendations/RecommendationsSection";
import { RisksSection } from "../assessments/risks/RisksSection";
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
  const { tab, focus } = useReportNav();

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
        <EvidenceProvider caseInfo={content.case} runId={record.run_id}>
          <ReportBody record={record} />
        </EvidenceProvider>
      </LegalBasisContext.Provider>
    </ReportIndexContext.Provider>
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
        <Link to="/">Danh sách ca</Link> / {kase.ca_id}
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
          {kase.assessment_context.loai_moc_ap_dung ?? "chưa rõ loại mốc"})
        </span>
      </div>
      {!mockEnabled && (
        <div className="actions">
          {(["pdf", "docx"] as const).map((format) => (
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
      {report.report_status !== "PUBLISHED" && (
        <Notice tone="warn">
          <strong>Kết quả máy, chưa được chuyên viên xác nhận.</strong> Báo cáo đang ở trạng thái{" "}
          {report.report_status} / review {report.review_status}; không dùng như kết luận pháp lý
          đã duyệt.
        </Notice>
      )}
      {mockEnabled && (
        <Notice tone="info">
          Dữ liệu mock: report tham chiếu QA (EXPECTED) dùng để dựng giao diện, không phải output
          của một lần chạy dev.
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
