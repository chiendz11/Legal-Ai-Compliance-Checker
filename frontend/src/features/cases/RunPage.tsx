import { Link, Navigate, useParams } from "react-router-dom";

import { useRunReports, useRunStatus } from "../../shared/api/queries";
import { Empty, LoadState, Notice, Section, StatusBadge } from "../../shared/components/ui";

const STAGE_LABELS: Record<string, string> = {
  INTAKE: "Tiếp nhận hồ sơ",
  DOCUMENT_INTELLIGENCE: "Trích xuất hợp đồng",
  SCOPE_RESOLUTION: "Xác định phạm vi",
  TEMPORAL_RESOLUTION: "Chọn phiên bản theo thời điểm",
  CITATION_VALIDATION: "Xác minh viện dẫn",
  RETRIEVAL: "Tìm bằng chứng",
  COMPLIANCE: "Đánh giá tuân thủ",
  RISK_AGGREGATION: "Tổng hợp rủi ro",
  RECOMMENDATION: "Khuyến nghị",
};

/** Plain-language cause for each failure reason the runner records. */
const FAILURE_HELP: Record<string, string> = {
  DOCUMENT_INTELLIGENCE_UNAVAILABLE:
    "Chưa có module đọc hợp đồng (nhóm A). Tệp đã được lưu an toàn; ca sẽ chạy được khi module được gộp.",
  MODULE_NOT_IMPLEMENTED: "Máy chủ chưa bật module đánh giá cho bước này.",
  REFERENCE_UNAVAILABLE: "Ca này không có dữ liệu tham chiếu để phát lại.",
  HANDOFF_VALIDATION_FAILED:
    "Dữ liệu bàn giao giữa hai bước không hợp lệ nên run dừng lại để không tạo kết luận sai.",
  UNEXPECTED_ERROR: "Lỗi ngoài dự kiến trong một module; xem trace để báo cho nhóm phụ trách.",
};

const STAGE_TONE: Record<string, string> = {
  PENDING: "neutral",
  RUNNING: "info",
  COMPLETED: "good",
  FAILED: "bad",
  SKIPPED: "neutral",
};

/** Run progress; once COMPLETED it opens the run's newest report version. */
export function RunPage() {
  const { caId = "", runId = "" } = useParams();
  const status = useRunStatus(caId, runId);
  const completed = status.data?.status === "COMPLETED";
  const reports = useRunReports(caId, runId, completed);
  if (!status.data) return <LoadState error={status.error} />;
  const run = status.data;
  const [latest] = reports.data?.items ?? [];
  if (completed && latest && reports.data?.total === 1) {
    return <Navigate replace to={`/reports/${latest.report.bao_cao_id}`} />;
  }
  return (
    <Section
      title={`Run ${runId}`}
      description={
        <>
          Ca <Link to="/">{caId}</Link> · cập nhật{" "}
          {new Date(run.updated_at).toLocaleTimeString("vi-VN")}
        </>
      }
    >
      <p>
        <StatusBadge kind="runStatus" code={run.status} />{" "}
        <span className="muted small">
          Hoàn tất nghĩa là đã có kết quả máy, chưa phải đã review hay phát hành.
        </span>
      </p>
      {run.error && (
        <Notice tone="bad">
          <strong>
            {run.error.details
              ?.map((d) => FAILURE_HELP[String(d.reason)])
              .find(Boolean) ?? "Run dừng do lỗi."}
          </strong>
          <br />
          <span className="small">{run.error.message}</span>
          <br />
          <span className="small">
            {run.error.details?.map((d) => String(d.reason ?? JSON.stringify(d))).join(", ")} ·
            trace <code>{run.error.trace_id}</code>
          </span>
        </Notice>
      )}
      <ol className="stages">
        {run.stages.map((s) => (
          <li key={s.stage} className={`stage tone-${STAGE_TONE[s.status] ?? "neutral"}`}>
            <span className="stage-name">{STAGE_LABELS[s.stage] ?? s.stage}</span>
            <span className="stage-status">{s.status}</span>
          </li>
        ))}
      </ol>
      {completed && (
        <>
          <h3 className="subhead">Phiên bản báo cáo</h3>
          {reports.data?.items.length ? (
            <ul>
              {reports.data.items.map(({ report, review_revision }) => (
                <li key={report.bao_cao_id}>
                  <Link to={`/reports/${report.bao_cao_id}`}>
                    {report.phien_ban_bao_cao} · review {review_revision}
                  </Link>{" "}
                  <StatusBadge kind="reportStatus" code={report.report_status} />
                </li>
              ))}
            </ul>
          ) : (
            <Empty>Run đã hoàn tất nhưng chưa có báo cáo.</Empty>
          )}
        </>
      )}
    </Section>
  );
}
