import type { ReportContent } from "../../shared/api/client";
import { requirementDisplayStatus } from "./assessmentStatus";
import { type Cause, explainRequirement } from "./explain";
import { useReportIndex } from "./reportIndex";

/** Causes of "insufficient" requirements with their counts, most frequent first. */
export function useInsufficientCauses(content: ReportContent) {
  const index = useReportIndex();
  const causes = new Map<Cause, { count: number; fields: Map<string, number> }>();
  for (const r of content.compliance.requirement_results) {
    // Rows outside the chosen review scope or not triggered keep their stored status but are
    // not "insufficient" for the reader.
    if (requirementDisplayStatus(r) !== "INSUFFICIENT") continue;
    const why = explainRequirement(
      r,
      index.applicableById.get(r.yeu_cau_ca_id),
      index.criteriaByRequirement.get(r.yeu_cau_ca_id) ?? [],
    );
    const entry = causes.get(why.cause) ?? { count: 0, fields: new Map() };
    entry.count += 1;
    for (const f of why.fields ?? []) entry.fields.set(f, (entry.fields.get(f) ?? 0) + 1);
    causes.set(why.cause, entry);
  }
  return [...causes].sort((a, b) => b[1].count - a[1].count);
}

/** What the reader can do about each cause; shown under "Việc nên làm tiếp". */
export const NEXT_STEP: Partial<Record<Cause, string>> = {
  NO_AI:
    "Lần chạy này chưa dùng AI đọc nội dung điều khoản. Liên hệ quản trị viên để bật AI rồi chạy lại hợp đồng từ danh sách.",
  PARTY:
    "Bổ sung các thông tin còn thiếu về giao dịch (ví dụ căn hộ có phải nhà xây mới, nhà ở xã hội) hoặc để chuyên viên xác nhận ở mục Rà soát.",
  MISSING_FACT:
    "Kiểm tra hợp đồng có ghi các thông tin còn thiếu không; nếu có, chuyên viên xác nhận ở mục Rà soát.",
  DATE: "Bổ sung ngày còn thiếu (ví dụ ngày thu tiền) nếu hợp đồng hoặc phụ lục có ghi.",
  NEEDS_REVIEWER:
    "Chuyên viên xác minh dữ kiện của các điểm kiểm tra còn chờ (điều kiện phát sinh, điều khoản bị cấm) và kết luận ở mục Rà soát.",
  AI_PENDING: "Chuyên viên xem các đề xuất của AI và xác nhận hoặc sửa ở mục Rà soát.",
  NO_EVIDENCE:
    "Kiểm tra hợp đồng có điều khoản tương ứng không; nếu có, đánh dấu ở mục Rà soát.",
  MARKER:
    "Không cần sửa hợp đồng vì các quy định này. Nếu cần kết luận ngay, chuyên viên tự xác định mốc thời gian và kết luận ở mục Rà soát.",
};
