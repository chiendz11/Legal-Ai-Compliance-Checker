import type { ReportRecord } from "../../shared/api/client";
import { Fields, JsonBlock, Notice, Section, Value } from "../../shared/components/ui";

export function AuditSection({ record }: { record: ReportRecord }) {
  const { report } = record;
  const content = report.report_json;
  const kase = content.case;
  const context = (content.audit as { context?: Record<string, unknown> }).context ?? {};
  return (
    <Section
      title="Audit và phiên bản"
      description="Snapshot tri thức, rule và run đã dùng để tái hiện báo cáo."
    >
      <Notice tone="info">
        Chưa có lịch sử review (C12): bước review chưa được triển khai. Report chỉ ở dạng draft.
      </Notice>
      <h3 className="subhead">Báo cáo</h3>
      <Fields
        rows={[
          ["Mã báo cáo", <code>{report.bao_cao_id}</code>],
          ["Phiên bản", <code>{report.phien_ban_bao_cao}</code>],
          ["Review revision", <code>{record.review_revision}</code>],
          ["Trạng thái", report.report_status],
          ["Review", report.review_status],
          ["File xuất", <Value value={report.report_uri} />],
        ]}
      />
      <h3 className="subhead">Ca đánh giá</h3>
      <Fields
        rows={[
          ["Ca", <code>{kase.ca_id}</code>],
          ["Hợp đồng", <code>{kase.hop_dong_id}</code>],
          ["Tenant", <code>{kase.tenant_id}</code>],
          ["Tạo bởi", kase.created_by],
          ["Tệp nguồn", <code>{kase.source.tep_id}</code>],
          ["SHA-256 nguồn", <code className="wrap">{kase.source.sha256}</code>],
          ["Phiên bản triển khai", <code>{kase.deployment.phien_ban_id}</code>],
          ["Rule", <code>{kase.deployment.rule_version}</code>],
          ["Tri thức pháp lý", <code>{kase.deployment.legal_knowledge_version}</code>],
        ]}
      />
      <h3 className="subhead">Ngữ cảnh run</h3>
      <Fields rows={Object.entries(context).map(([k, v]) => [k, <Value value={v} />])} />
      <h3 className="subhead">Tổng hợp (overall_summary)</h3>
      <JsonBlock value={content.overall_summary} />
    </Section>
  );
}
