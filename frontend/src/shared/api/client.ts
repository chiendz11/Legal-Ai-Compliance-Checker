import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

/** Same-origin client: Vite proxies /api and /health to the backend; MSW mocks planned routes. */
export const api = createClient<paths>({ baseUrl: "" });

type Schemas = components["schemas"];
export type CaseRecord = Schemas["Output_CaseRecord"];
export type AssessmentCase = Schemas["Output_AssessmentCase"];
export type RunProgress = Schemas["Output_RunProgress"];
export type CaseCreate = Schemas["Input_CaseCreate"];
export type ApiErrorBody = Schemas["Input_ApiError"];

/**
 * The backend writes envelope messages in English for engineers (api/errors.py). Readers get a
 * Vietnamese sentence chosen by message pattern first, then by error code; an unknown message
 * is passed through so nothing is hidden.
 */
const MESSAGE_VI: [RegExp, string][] = [
  [/Only PDF or DOCX/i, "Chỉ nhận tệp hợp đồng dạng PDF hoặc DOCX."],
  [/exceeds \d+ bytes|too large/i, "Tệp vượt quá dung lượng cho phép (tối đa 100 MB)."],
  [/Too many failed sign-in/i, "Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau ít phút."],
  [/Wrong user ID or password/i, "Sai mã người dùng hoặc mật khẩu."],
  [/Authentication is disabled/i, "Máy chủ đang tắt chức năng đăng nhập."],
  [/requires the \w+ role/i, "Tài khoản của bạn không có quyền thực hiện thao tác này."],
  [/no pinned knowledge snapshot/i, "Báo cáo này thiếu phiên bản kho tri thức nên không thao tác được."],
  [/Source unavailable/i, "Không lấy được tệp hợp đồng gốc từ nơi lưu trữ."],
];

const CODE_VI: Record<string, string> = {
  UNAUTHENTICATED: "Bạn cần đăng nhập để tiếp tục.",
  FORBIDDEN: "Tài khoản của bạn không có quyền thực hiện thao tác này.",
  NOT_FOUND: "Không tìm thấy dữ liệu yêu cầu (có thể đã bị xóa hoặc đường dẫn sai).",
  FILE_TOO_LARGE: "Tệp vượt quá dung lượng cho phép (tối đa 100 MB).",
  UNSUPPORTED_MEDIA_TYPE: "Chỉ nhận tệp hợp đồng dạng PDF hoặc DOCX.",
  RESULT_NOT_READY: "Lần phân tích này chưa xong nên chưa có kết quả.",
  STALE_REVIEW: "Mục này vừa được người khác rà soát. Trang đã tải lại trạng thái mới, hãy kiểm tra rồi gửi lại.",
  REVIEW_REQUIRED: "Báo cáo còn mục chưa rà soát nên chưa phát hành được.",
  VALIDATION_ERROR: "Dữ liệu gửi lên chưa hợp lệ. Kiểm tra lại các trường rồi thử lại.",
  CONFLICT: "Thao tác xung đột với trạng thái hiện tại. Tải lại trang rồi thử lại.",
  INTERNAL_ERROR: "Máy chủ gặp lỗi khi xử lý. Thử lại sau; nếu vẫn lỗi, báo nhóm kỹ thuật.",
};

/** Human-readable (Vietnamese) message from the API error envelope, if the error carries one. */
export function apiErrorMessage(error: unknown): string | null {
  const body = (error as { body?: Partial<ApiErrorBody> } | null)?.body;
  const message = body?.error?.message ?? null;
  const code = body?.error?.code ?? null;
  const byMessage = message ? MESSAGE_VI.find(([pattern]) => pattern.test(message)) : undefined;
  if (byMessage) return byMessage[1];
  if (code && CODE_VI[code]) return CODE_VI[code];
  return message;
}

/** Error code from the envelope (STALE_REVIEW, REVIEW_REQUIRED, ...), if any. */
export function apiErrorCode(error: unknown): string | null {
  const body = (error as { body?: Partial<ApiErrorBody> } | null)?.body;
  return body?.error?.code ?? null;
}
export type ReportRecord = Schemas["Output_ReportRecord"];
export type FinalReport = Schemas["Output_FinalReport"];
export type ReportContent = Schemas["Output_ReportContent"];
export type ContractProfile = Schemas["Output_ContractProfile"];
export type ProfileEvidence = Schemas["Output_ProfileEvidence"];
export type ApplicableRequirement = Schemas["Output_ApplicableRequirement"];
export type ScopeResolution = Schemas["Output_ScopeResolution"];
export type RequirementResult = Schemas["Output_RequirementResult"];
export type CriterionResult = Schemas["Output_CriterionResult"];
export type Evidence = Schemas["Output_Evidence"];
export type CitationExtraction = Schemas["Output_CitationExtraction"];
export type CitationValidation = Schemas["Output_CitationValidation"];
export type RiskResult = Schemas["Output_RiskResult"];
export type Recommendation = Schemas["Output_Recommendation"];
export type LegalBasisItem = Schemas["Output_LegalBasisItem"];
export type AssessmentDraft = Schemas["Output_AssessmentDraft"];
export type Chunk = Schemas["Output_Chunk"];
export type SessionInfo = Schemas["Output_SessionInfo"];
export type RunReviewState = Schemas["Output_RunReviewState"];
export type TargetReviewState = Schemas["Output_TargetReviewState"];
export type ReviewRecord = Schemas["Output_ReviewRecord"];
export type ReviewCreate = Schemas["Input_ReviewCreate"];
export type ReviewAction = ReviewCreate["action"];
export type Page<T> = { items: T[]; page: number; page_size: number; total: number };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`API ${status}`);
  }
}

/** Unwrap an openapi-fetch result, turning error responses into ApiError for React Query. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined) throw new ApiError(result.response.status, result.error);
  return result.data;
}
