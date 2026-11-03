import { Link, Navigate, useParams } from "react-router-dom";

import { useRunReports, useRunStatus } from "../../shared/api/queries";
import { Empty, Fields, LoadState, Notice, Section, StatusBadge } from "../../shared/components/ui";

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

/** One-line cause shown under the failed step. */
const FAILURE_SHORT: Record<string, string> = {
  DOCUMENT_INTELLIGENCE_UNAVAILABLE: "Chưa có module đọc hợp đồng (nhóm A)",
  MODULE_NOT_IMPLEMENTED: "Bước này chưa được bật trên máy chủ",
  REFERENCE_UNAVAILABLE: "Ca này không có dữ liệu tham chiếu",
  HANDOFF_VALIDATION_FAILED: "Dữ liệu bàn giao giữa hai bước không hợp lệ",
  UNEXPECTED_ERROR: "Lỗi ngoài dự kiến · xem trace bên trên",
};

const STAGE_STATUS: Record<string, string> = {
  PENDING: "Chờ",
  RUNNING: "Đang chạy",
  COMPLETED: "Hoàn tất",
  FAILED: "Lỗi",
  SKIPPED: "Bỏ qua",
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
  const done = run.stages.filter((s) => s.status === "COMPLETED").length;
  const reason = run.error?.details?.map((d) => String(d.reason)).find((r) => r in FAILURE_SHORT);
  const failed = run.status === "FAILED";
  return (
    <Section
      title="Tiến độ đánh giá"
      description={
        <>
          Ca <Link to={`/?q=${encodeURIComponent(caId)}`}>{caId}</Link> · run <code>{runId}</code>
        </>
      }
    >
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
      <div className="run-grid">
        <ol className="stages">
          {run.stages.map((s) => {
            // Steps after a failure never ran; say so instead of "waiting".
            const skipped = failed && s.status === "PENDING";
            const note =
              s.status === "FAILED"
                ? (reason && FAILURE_SHORT[reason]) || "Run dừng tại bước này"
                : s.status === "RUNNING"
                  ? "Đang xử lý…"
                  : null;
            return (
              <li key={s.stage} className={`stage tone-${STAGE_TONE[s.status] ?? "neutral"}`}>
                {(s.status === "FAILED" || s.status === "RUNNING") && (
                  <span className="stage-ping" aria-hidden="true" />
                )}
                <span className="stage-name">
                  {STAGE_LABELS[s.stage] ?? s.stage}
                  {note && <small className="stage-note">{note}</small>}
                </span>
                <span className="stage-status" title={s.status}>
                  {skipped ? "Không chạy" : (STAGE_STATUS[s.status] ?? s.status)}
                </span>
              </li>
            );
          })}
        </ol>
        <aside className="card-flat run-side">
          <div className="run-side-head">
            <StatusBadge kind="runStatus" code={run.status} />
            <span className="muted small">
              {done}/{run.stages.length} bước xong
            </span>
          </div>
          <Fields
            rows={[
              ["Cập nhật", new Date(run.updated_at).toLocaleString("vi-VN")],
              ["Phiên bản triển khai", <code>{run.context.phien_ban_id}</code>],
              ["Rule", <code>{run.context.rule_version}</code>],
              ["Tri thức pháp lý", <code>{run.context.legal_knowledge_version}</code>],
            ]}
          />
          {run.status !== "FAILED" && (
            <p className="muted small">
              Hoàn tất nghĩa là đã có kết quả máy, chưa phải đã review hay phát hành.
            </p>
          )}
          {completed && (
            <>
              <h3 className="subhead">Phiên bản báo cáo</h3>
              {reports.data?.items.length ? (
                <div className="stack">
                  {reports.data.items.map(({ report, review_revision }) => (
                    <Link
                      key={report.bao_cao_id}
                      className="version-row"
                      to={`/reports/${report.bao_cao_id}`}
                    >
                      <span>
                        {report.phien_ban_bao_cao}
                        <span className="muted small"> · review {review_revision}</span>
                      </span>
                      <StatusBadge kind="reportStatus" code={report.report_status} />
                    </Link>
                  ))}
                </div>
              ) : (
                <Empty>
                  {reports.isFetching
                    ? "Đang lấy báo cáo của run…"
                    : "Run đã hoàn tất nhưng chưa có báo cáo."}
                </Empty>
              )}
            </>
          )}
        </aside>
      </div>
    </Section>
  );
}
