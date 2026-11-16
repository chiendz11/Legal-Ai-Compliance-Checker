/** Display labels only; statuses always come from the backend and are never recomputed here. */
export type Tone = "good" | "warn" | "bad" | "unknown" | "info" | "neutral";
type Label = { text: string; tone: Tone };

const table: Record<string, Record<string, Label>> = {
  requirement: {
    OUTSIDE_REVIEW_SCOPE: { text: "Ngoài phạm vi rà soát dự thảo", tone: "neutral" },
    NOT_TRIGGERED: { text: "Không phát sinh điều kiện", tone: "neutral" },
    COMPLIANT: { text: "Tuân thủ", tone: "good" },
    PARTIAL: { text: "Tuân thủ một phần", tone: "warn" },
    NON_COMPLIANT: { text: "Không tuân thủ", tone: "bad" },
    INSUFFICIENT: { text: "Chưa đủ căn cứ", tone: "unknown" },
  },
  criterion: {
    OUTSIDE_REVIEW_SCOPE: { text: "Ngoài phạm vi rà soát dự thảo", tone: "neutral" },
    EXCLUDED: { text: "Không áp dụng theo điều kiện", tone: "neutral" },
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
  reasonCode: {
    IN_FORCE_AT_DATE: { text: "Văn bản đang có hiệu lực tại ngày ký kết", tone: "good" },
    REPLACED_BEFORE_DATE: { text: "Văn bản đã bị thay thế trước ngày ký kết", tone: "bad" },
    EXPIRED_BEFORE_DATE: { text: "Văn bản đã hết hiệu lực trước ngày ký kết", tone: "bad" },
    NOT_YET_IN_FORCE_AT_DATE: { text: "Văn bản chưa có hiệu lực tại ngày ký kết", tone: "warn" },
    RELEVANT_DATE_UNKNOWN: { text: "Chưa rõ ngày ký kết để xác minh hiệu lực", tone: "unknown" },
    EFFECTIVE_DATE_UNKNOWN: { text: "Chưa xác định được ngày hiệu lực", tone: "unknown" },
    CATALOG_NUMBER_MATCH: { text: "Khớp số hiệu trong danh mục luật", tone: "good" },
    CATALOG_TITLE_YEAR_MATCH: { text: "Khớp tên luật và năm ban hành", tone: "good" },
    CONTRACT_NUMBER_ANCHOR_MATCH: { text: "Liên kết theo mỏ neo số hiệu trong hợp đồng", tone: "good" },
    NAME_ONLY_VERSION_IDENTITY_AMBIGUOUS: { text: "Chỉ nêu tên văn bản, chưa đủ thông tin xác định phiên bản", tone: "warn" },
    NUMBER_NOT_IN_CATALOG: { text: "Số hiệu chưa có trong danh mục luật", tone: "warn" },
    NUMBER_TITLE_MISMATCH: { text: "Tên văn bản không khớp với số hiệu", tone: "bad" },
    NUMBER_YEAR_MISMATCH: { text: "Năm ban hành không khớp với số hiệu", tone: "bad" },
    MULTIPLE_CATALOG_CANDIDATES: { text: "Trùng lặp nhiều văn bản trong danh mục", tone: "warn" },
  },
  docStatus: {
    HISTORICAL: { text: "Hết hiệu lực (đã có luật mới thay thế)", tone: "warn" },
    CURRENT: { text: "Đang có hiệu lực hiện hành", tone: "good" },
    AMENDED_PARTIAL: { text: "Đang có hiệu lực (đã sửa đổi một phần)", tone: "info" },
    CHUA_XAC_MINH_TOAN_BO_SUA_DOI: { text: "Đang hiệu lực (cần rà soát sửa đổi)", tone: "neutral" },
    BAN_HOP_NHAT_KHONG_TAO_HIEU_LUC_MOI: { text: "Văn bản hợp nhất (tra cứu)", tone: "neutral" },
    SOURCE_CHECKED: { text: "Đã kiểm tra nguồn", tone: "info" },
    CURRENT_CHECKED_METADATA: { text: "Đang có hiệu lực hiện hành", tone: "good" },
    CURRENT_CORE_LIST_CHECKED: { text: "Đang có hiệu lực (danh mục chuẩn)", tone: "good" },
  },
  actionType: {
    SUA_DOI_DIEU_KHOAN: { text: "Sửa đổi điều khoản", tone: "bad" },
    BO_SUNG_DIEU_KHOAN: { text: "Bổ sung điều khoản", tone: "warn" },
    THAY_THE_CAN_CU: { text: "Cập nhật căn cứ pháp luật", tone: "info" },
    VERIFY: { text: "Xác minh thực tế", tone: "unknown" },
    VERIFY_REFERENCE: { text: "Xác minh viện dẫn pháp luật", tone: "unknown" },
    REQUEST_EVIDENCE: { text: "Yêu cầu bổ sung tài liệu", tone: "warn" },
    REQUEST_VERIFICATION: { text: "Yêu cầu xác minh", tone: "warn" },
    THOA_THUAN_LAI: { text: "Thỏa thuận lại điều khoản", tone: "warn" },
  },
  review: {
    PENDING: { text: "Chưa review", tone: "unknown" },
    IN_REVIEW: { text: "Đang review", tone: "warn" },
    APPROVED: { text: "Đã duyệt", tone: "good" },
  },
  knowledgeReview: {
    HUMAN_VERIFIED: { text: "Tri thức đã được con người duyệt", tone: "good" },
    SOURCE_CHECKED: { text: "Tri thức đã kiểm tra nguồn", tone: "info" },
    DEV_UNVERIFIED: { text: "Tri thức chưa được xác minh", tone: "unknown" },
    PENDING_HUMAN_REVIEW: { text: "Tri thức chờ người duyệt", tone: "unknown" },
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
    NGAY_GIAO_KET: { text: "Ngày giao kết", tone: "neutral" },
    NGAY_HIEU_LUC: { text: "Ngày hiệu lực", tone: "neutral" },
    NGAY_SU_KIEN: { text: "Ngày phát sinh sự kiện", tone: "neutral" },
    SIGNING: { text: "Ngày ký kết", tone: "neutral" },
    DEPOSIT_AGREEMENT: { text: "Mốc thỏa thuận đặt cọc", tone: "neutral" },
    HANDOVER: { text: "Mốc bàn giao", tone: "neutral" },
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

/** Converts technical citation ID like HD_UP_..._VD_..._007 to user-friendly "Viện dẫn #7" */
export function shortCitationId(id: string | null | undefined): string {
  if (!id) return "Viện dẫn";
  const match = id.match(/_0*([1-9]\d*)$/);
  if (match) return `Viện dẫn #${match[1]}`;
  const vdMatch = id.match(/VD_[a-f0-9]+_0*([1-9]\d*)/i);
  if (vdMatch) return `Viện dẫn #${vdMatch[1]}`;
  return id.length > 20 ? `${id.slice(0, 10)}...${id.slice(-6)}` : id;
}

/** Formats technical knowledge snapshot string into a readable title */
export function friendlyKnowledgeVersion(version: string | null | undefined): string {
  if (!version) return "Tri thức pháp luật chuẩn hóa";
  if (version.includes("V750") || version.includes("20261110")) {
    return "Kho tri thức pháp luật Việt Nam (Bản chuẩn hóa 2026)";
  }
  return `Kho tri thức: ${version}`;
}
