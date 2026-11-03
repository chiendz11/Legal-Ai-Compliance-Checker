import type { ReportRecord } from "../../shared/api/client";
import { useReviews } from "../../shared/api/queries";
import {
  Empty,
  Fields,
  JsonBlock,
  LoadState,
  Notice,
  Section,
  StatusBadge,
  Table,
  Value,
} from "../../shared/components/ui";
import { mockEnabled } from "../../shared/env";

export function AuditSection({ record }: { record: ReportRecord }) {
  const { report } = record;
  const content = report.report_json;
  const kase = content.case;
  const audit = content.audit as {
    context?: Record<string, unknown>;
    publication?: Record<string, unknown>;
  };
  const context = audit.context ?? {};
  const publication = audit.publication;
  return (
    <Section
      title="Audit và phiên bản"
      description="Snapshot tri thức, rule và run đã dùng để tái hiện báo cáo."
    >
      {publication && (
        <>
          <h3 className="subhead">Phát hành</h3>
          <Fields rows={Object.entries(publication).map(([k, v]) => [k, <Value value={v} />])} />
        </>
      )}
      <h3 className="subhead">Báo cáo</h3>
      <Fields
        rows={[
          ["Mã báo cáo", <code>{report.bao_cao_id}</code>],
          ["Phiên bản", <code>{report.phien_ban_bao_cao}</code>],
          ["Review revision", <code>{record.review_revision}</code>],
          ["Trạng thái", <StatusBadge kind="reportStatus" code={report.report_status} />],
          ["Review", <StatusBadge kind="review" code={report.review_status} />],
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
      <h3 className="subhead">Lịch sử review (C12)</h3>
      {mockEnabled ? (
        <Notice tone="info">Lịch sử review cần backend thật.</Notice>
      ) : (
        <ReviewHistory caId={report.ca_id} runId={record.run_id} />
      )}
      <h3 className="subhead">Tổng hợp (overall_summary)</h3>
      <JsonBlock value={content.overall_summary} />
    </Section>
  );
}

/** Append-only events of the whole run, including ones newer than this report version. */
function ReviewHistory({ caId, runId }: { caId: string; runId: string }) {
  const { data, error } = useReviews(caId, runId);
  if (!data) return <LoadState error={error} />;
  if (data.items.length === 0) return <Empty>Chưa có review nào cho run này.</Empty>;
  return (
    <Table>
      <thead>
        <tr>
          <th>Thời điểm</th>
          <th>Người review</th>
          <th>Đối tượng</th>
          <th>Quyết định</th>
          <th>Giá trị mới</th>
          <th>Lý do</th>
        </tr>
      </thead>
      <tbody>
        {data.items.map(({ review }) => (
          <tr key={review.review_id}>
            <td>{new Date(review.reviewed_at).toLocaleString("vi-VN")}</td>
            <td>
              <code>{review.actor_id}</code>
            </td>
            <td>
              {review.target.doi_tuong_loai}
              <br />
              <code className="small">{review.target.doi_tuong_id}</code>
            </td>
            <td>
              <StatusBadge kind="reviewAction" code={review.action} />
            </td>
            <td>
              {Object.keys(review.after).length ? <JsonBlock value={review.after} /> : "—"}
            </td>
            <td>{review.reason}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
