/** Display labels only; statuses always come from the backend and are never recomputed here. */
export type Tone = "good" | "warn" | "bad" | "unknown" | "info" | "neutral";
type Label = { text: string; tone: Tone };

const table: Record<string, Record<string, Label>> = {
  requirement: {
    COMPLIANT: { text: "Tuân thủ", tone: "good" },
    PARTIAL: { text: "Tuân thủ một phần", tone: "warn" },
    NON_COMPLIANT: { text: "Không tuân thủ", tone: "bad" },
    INSUFFICIENT: { text: "Chưa đủ căn cứ", tone: "unknown" },
  },
  criterion: {
    SATISFIED: { text: "Đáp ứng", tone: "good" },
    MISSING: { text: "Thiếu nội dung", tone: "warn" },
    VIOLATED: { text: "Vi phạm", tone: "bad" },
    UNKNOWN: { text: "Chưa xác định", tone: "unknown" },
  },
  citation: {
    VALID: { text: "Hợp lệ", tone: "good" },
    STALE: { text: "Hết hiệu lực / bị thay thế", tone: "warn" },
    INVALID: { text: "Không hợp lệ", tone: "bad" },
    UNKNOWN: { text: "Chưa xác minh", tone: "unknown" },
  },
  domain: {
    MATCH: { text: "Đúng lĩnh vực", tone: "good" },
    MISMATCH: { text: "Sai lĩnh vực", tone: "bad" },
    UNKNOWN: { text: "Lĩnh vực chưa rõ", tone: "unknown" },
  },
  extraction: {
    EXTRACTED: { text: "Đã trích xuất", tone: "neutral" },
    AMBIGUOUS: { text: "Mơ hồ", tone: "warn" },
    UNKNOWN: { text: "Chưa rõ", tone: "unknown" },
  },
  severity: {
    LOW: { text: "Thấp", tone: "info" },
    MEDIUM: { text: "Trung bình", tone: "warn" },
    HIGH: { text: "Cao", tone: "bad" },
    CRITICAL: { text: "Nghiêm trọng", tone: "bad" },
    REVIEW_REQUIRED: { text: "Cần review", tone: "unknown" },
  },
  riskType: {
    COMPLIANCE: { text: "Tuân thủ", tone: "neutral" },
    CITATION: { text: "Viện dẫn", tone: "neutral" },
    VERIFICATION: { text: "Cần xác minh", tone: "neutral" },
  },
  reportStatus: {
    DRAFT: { text: "Bản nháp", tone: "warn" },
    REVIEW_REQUIRED: { text: "Chờ review", tone: "warn" },
    PUBLISHED: { text: "Đã phát hành", tone: "good" },
  },
  review: {
    PENDING: { text: "Chưa review", tone: "unknown" },
    IN_REVIEW: { text: "Đang review", tone: "warn" },
    APPROVED: { text: "Đã duyệt", tone: "good" },
  },
  reviewAction: {
    CONFIRM: { text: "Đã xác nhận", tone: "good" },
    OVERRIDE: { text: "Đã chỉnh sửa", tone: "info" },
    REQUEST_MORE_EVIDENCE: { text: "Yêu cầu bổ sung", tone: "warn" },
    REJECT: { text: "Bác bỏ", tone: "bad" },
    COMMENT: { text: "Ghi chú", tone: "neutral" },
  },
  scope: {
    MATCH: { text: "Thuộc phạm vi", tone: "good" },
    NO_MATCH: { text: "Ngoài phạm vi", tone: "neutral" },
    UNKNOWN: { text: "Phạm vi chưa rõ", tone: "unknown" },
  },
  version: {
    RESOLVED: { text: "Đã chọn phiên bản", tone: "good" },
    UNKNOWN: { text: "Phiên bản chưa rõ", tone: "unknown" },
  },
  applicability: {
    CONFIRMED: { text: "Áp dụng", tone: "good" },
    NOT_APPLICABLE: { text: "Không áp dụng", tone: "neutral" },
    UNKNOWN: { text: "Chưa xác nhận áp dụng", tone: "unknown" },
  },
  anchor: {
    NGAY_GIAO_KET: { text: "ngày giao kết", tone: "neutral" },
    NGAY_HIEU_LUC: { text: "ngày hiệu lực", tone: "neutral" },
    NGAY_SU_KIEN: { text: "ngày phát sinh sự kiện", tone: "neutral" },
  },
  markerType: {
    SIGNING: { text: "Ký kết", tone: "neutral" },
    EXPECTED_HANDOVER: { text: "Dự kiến bàn giao", tone: "neutral" },
    COLLECTION: { text: "Thu tiền", tone: "neutral" },
    PRE_HANDOVER_COLLECTION: { text: "Thu tiền trước bàn giao", tone: "neutral" },
    PRE_CERTIFICATE_COLLECTION: { text: "Thu tiền trước khi cấp giấy chứng nhận", tone: "neutral" },
  },
  precision: {
    DAY: { text: "Theo ngày", tone: "neutral" },
    MONTH: { text: "Theo tháng", tone: "neutral" },
    YEAR: { text: "Theo năm", tone: "neutral" },
    UNKNOWN: { text: "Chưa rõ", tone: "unknown" },
  },
  markerStatus: {
    EXTRACTED: { text: "Đã trích xuất", tone: "neutral" },
    SYNTHETIC_SOURCE_EXTRACTED: { text: "Trích từ nguồn (dữ liệu tổng hợp)", tone: "neutral" },
    UNKNOWN: { text: "Chưa xác định", tone: "unknown" },
  },
  runStatus: {
    QUEUED: { text: "Đang chờ", tone: "info" },
    RUNNING: { text: "Đang chạy", tone: "info" },
    COMPLETED: { text: "Hoàn tất", tone: "good" },
    FAILED: { text: "Lỗi", tone: "bad" },
  },
};

export type LabelKind = keyof typeof table;

/** Unknown codes stay visible as-is instead of being hidden or mapped to a friendlier status. */
export function label(kind: LabelKind, code: string | null | undefined): Label {
  if (code == null) return { text: "Không có dữ liệu", tone: "unknown" };
  return table[kind]?.[code] ?? { text: code, tone: "neutral" };
}
