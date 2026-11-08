import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { useCases, useRunReports, useRunStatus, useStartRun } from "../../shared/api/queries";
import {
  Disclosure,
  Empty,
  Fields,
  LoadState,
  Section,
  StatusBadge,
} from "../../shared/components/ui";

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
    "Không đọc được tệp hợp đồng gốc: tệp không còn trên máy chủ. Hãy tải lại tệp.",
  DOCUMENT_FORMAT_UNSUPPORTED:
    "Hệ thống hiện chỉ đánh giá được tệp PDF. Hãy tải bản PDF của hợp đồng này.",
  DOCUMENT_NOT_READABLE:
    "Không đọc được chữ nào trong tệp, kể cả bằng OCR: bản scan trống, quá mờ, hoặc máy chủ chưa bật OCR tiếng Việt. Hãy tải bản scan rõ hơn hoặc PDF có chữ.",
  CONTRACT_TYPE_UNSUPPORTED:
    "Tài liệu này không phải hợp đồng mua bán căn hộ chung cư (không tìm thấy tiêu đề “HỢP ĐỒNG MUA BÁN CĂN HỘ”). Hệ thống hiện chỉ đánh giá loại hợp đồng này nên không xử lý tiếp.",
  OCR_FAILED:
    "Đây là bản scan nhưng bước OCR bị lỗi (quá thời gian hoặc ảnh hỏng). Hãy thử chạy lại; nếu vẫn lỗi, tải bản PDF có chữ.",
  SOURCE_INTEGRITY_FAILED:
    "Tệp trên máy chủ không khớp dấu vân tay (SHA-256) đã lưu, nên hệ thống dừng để không đánh giá nhầm tài liệu.",
  MODULE_NOT_IMPLEMENTED: "Máy chủ chưa bật module đánh giá. Hãy báo nhóm kỹ thuật.",
  REFERENCE_UNAVAILABLE: "Ca này không có dữ liệu tham chiếu để phát lại.",
  HANDOFF_VALIDATION_FAILED:
    "Có lỗi dữ liệu giữa hai bước xử lý nên hệ thống dừng lại để không tạo kết luận sai. Hãy báo nhóm kỹ thuật.",
  UNEXPECTED_ERROR:
    "Lỗi ngoài dự kiến. Hãy thử chạy lại; nếu vẫn lỗi, báo nhóm kỹ thuật kèm mã trace trong phần chi tiết kỹ thuật.",
};

/** One-line cause shown on the step where the run stopped. */
const FAILURE_SHORT: Record<string, string> = {
  DOCUMENT_INTELLIGENCE_UNAVAILABLE: "Không đọc được tệp hợp đồng gốc",
  DOCUMENT_FORMAT_UNSUPPORTED: "Chỉ đọc được PDF, chưa đọc DOCX",
  DOCUMENT_NOT_READABLE: "Không đọc được chữ, kể cả bằng OCR",
  CONTRACT_TYPE_UNSUPPORTED: "Không phải hợp đồng mua bán căn hộ",
  OCR_FAILED: "OCR bản scan bị lỗi",
  SOURCE_INTEGRITY_FAILED: "Tệp không khớp SHA-256 đã lưu",
  MODULE_NOT_IMPLEMENTED: "Bước này chưa được bật trên máy chủ",
  REFERENCE_UNAVAILABLE: "Ca này không có dữ liệu tham chiếu",
  HANDOFF_VALIDATION_FAILED: "Lỗi dữ liệu giữa hai bước",
  UNEXPECTED_ERROR: "Lỗi ngoài dự kiến",
};

const STAGE_STATUS: Record<string, string> = {
  PENDING: "Chờ",
  RUNNING: "Đang chạy",
  COMPLETED: "Xong",
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

/** The nine pipeline stages as four steps a reader understands. */
const STEPS: { title: string; detail: string; stages: string[] }[] = [
  {
    title: "Đọc hợp đồng",
    detail: "Đọc chữ trong tệp (OCR nếu là bản scan), tìm loại hợp đồng, các bên, ngày ký, giá…",
    stages: ["INTAKE", "DOCUMENT_INTELLIGENCE"],
  },
  {
    title: "Xác định quy định áp dụng",
    detail: "Chọn các quy định dành cho loại hợp đồng này và điều luật có hiệu lực tại ngày ký.",
    stages: ["SCOPE_RESOLUTION", "TEMPORAL_RESOLUTION"],
  },
  {
    title: "Kiểm tra từng điều khoản",
    detail: "Tìm đoạn hợp đồng liên quan cho từng điểm kiểm tra, đối chiếu các luật hợp đồng trích dẫn.",
    stages: ["CITATION_VALIDATION", "RETRIEVAL", "COMPLIANCE"],
  },
  {
    title: "Tổng hợp rủi ro và khuyến nghị",
    detail: "Gom kết quả thành rủi ro, gợi ý xử lý và báo cáo.",
    stages: ["RISK_AGGREGATION", "RECOMMENDATION"],
  },
];

type Stage = { stage: string; status: string };

function stepStatus(stages: Stage[], codes: string[], failed: boolean) {
  const mine = stages.filter((s) => codes.includes(s.stage));
  if (mine.some((s) => s.status === "FAILED")) return "FAILED";
  if (mine.some((s) => s.status === "RUNNING")) return "RUNNING";
  if (mine.length && mine.every((s) => s.status === "COMPLETED" || s.status === "SKIPPED"))
    return "COMPLETED";
  if (mine.some((s) => s.status === "COMPLETED")) return failed ? "NOT_RUN" : "RUNNING";
  return failed ? "NOT_RUN" : "PENDING";
}

const STEP_STATUS: Record<string, [string, string]> = {
  PENDING: ["Chờ", "neutral"],
  RUNNING: ["Đang chạy…", "info"],
  COMPLETED: ["Xong", "good"],
  FAILED: ["Dừng ở đây", "bad"],
  NOT_RUN: ["Không chạy", "neutral"],
};

/** Run progress in plain steps; once COMPLETED it opens the run's newest report version. */
export function RunPage() {
  const { caId = "", runId = "" } = useParams();
  const status = useRunStatus(caId, runId);
  const completed = status.data?.status === "COMPLETED";
  const reports = useRunReports(caId, runId, completed);
  const navigate = useNavigate();
  const startRun = useStartRun();
  const cases = useCases({ q: caId, page_size: 1 });
  const name = cases.data?.items.find((i) => i.case.ca_id === caId)?.ten_tai_lieu;
  if (!status.data) return <LoadState error={status.error} />;
  const run = status.data;
  const [latest] = reports.data?.items ?? [];
  if (completed && latest && reports.data?.total === 1) {
    return <Navigate replace to={`/reports/${latest.report.bao_cao_id}`} />;
  }
  const failed = run.status === "FAILED";
  const reason = run.error?.details?.map((d) => String(d.reason)).find((r) => r in FAILURE_SHORT);
  const help = run.error?.details?.map((d) => FAILURE_HELP[String(d.reason)]).find(Boolean);
  const title = failed
    ? "Không phân tích được hợp đồng này"
    : completed
      ? "Đã phân tích xong"
      : "Đang phân tích hợp đồng…";
  const retry = () =>
    startRun.mutate(caId, {
      onSuccess: (accepted) => navigate(`/cases/${caId}/runs/${accepted.context.run_id}`),
    });
  return (
    <Section
      title={title}
      description={
        <>
          <Link to="/">Hợp đồng</Link> / {name ?? caId}
          {!failed && !completed && (
            <>
              {" "}
              · Thường mất từ vài chục giây đến vài phút. Trang tự cập nhật; bạn có thể rời đi và
              quay lại sau.
            </>
          )}
        </>
      }
    >
      {failed && (
        <div className="failure">
          <p className="failure-title">{help ?? "Lần phân tích dừng do lỗi."}</p>
          <div className="actions">
            <Link className="button primary" to="/upload">
              Tải tệp khác
            </Link>
            <button type="button" className="button" disabled={startRun.isPending} onClick={retry}>
              Thử chạy lại
            </button>
            <Link className="button ghost" to="/">
              Về danh sách hợp đồng
            </Link>
          </div>
        </div>
      )}

      <ol className="steps">
        {STEPS.map((step, i) => {
          const code = stepStatus(run.stages, step.stages, failed);
          const [text, tone] = STEP_STATUS[code] ?? ["", "neutral"];
          return (
            <li key={step.title} className={`step tone-${tone}`}>
              <span className="step-num">{code === "COMPLETED" ? "✓" : i + 1}</span>
              <span className="step-body">
                <strong>{step.title}</strong>
                <span className="muted small">
                  {code === "FAILED" && reason ? FAILURE_SHORT[reason] : step.detail}
                </span>
              </span>
              <span className={`badge tone-${tone}`}>{text}</span>
            </li>
          );
        })}
      </ol>

      {completed && (
        <>
          <h3 className="subhead">Các phiên bản báo cáo</h3>
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
                    <span className="muted small"> · rà soát {review_revision}</span>
                  </span>
                  <StatusBadge kind="reportStatus" code={report.report_status} />
                </Link>
              ))}
            </div>
          ) : (
            <Empty>
              {reports.isFetching ? "Đang lấy báo cáo…" : "Đã chạy xong nhưng chưa có báo cáo."}
            </Empty>
          )}
        </>
      )}

      <Disclosure summary="Chi tiết kỹ thuật (dành cho kỹ sư)">
        <ol className="stages">
          {run.stages.map((s) => (
            <li key={s.stage} className={`stage tone-${STAGE_TONE[s.status] ?? "neutral"}`}>
              <span className="stage-name">{STAGE_LABELS[s.stage] ?? s.stage}</span>
              <span className="stage-status" title={s.status}>
                {failed && s.status === "PENDING"
                  ? "Không chạy"
                  : (STAGE_STATUS[s.status] ?? s.status)}
              </span>
            </li>
          ))}
        </ol>
        <Fields
          rows={[
            ["Mã ca / lần chạy", <code>{`${caId} · ${runId}`}</code>],
            ["Cập nhật", new Date(run.updated_at).toLocaleString("vi-VN")],
            ["Phiên bản triển khai", <code>{run.context.phien_ban_id}</code>],
            ["Bộ quy tắc", <code>{run.context.rule_version}</code>],
            ["Tri thức pháp lý", <code>{run.context.legal_knowledge_version}</code>],
          ]}
        />
        {run.error && (
          <p className="small">
            {run.error.message} ·{" "}
            {run.error.details?.map((d) => String(d.reason ?? JSON.stringify(d))).join(", ")} ·
            trace <code>{run.error.trace_id}</code>
          </p>
        )}
      </Disclosure>
    </Section>
  );
}
