import type { ReportRecord } from "../../shared/api/client";
import { Notice } from "../../shared/components/ui";
import { ChecklistSection } from "../assessments/checklist/ChecklistSection";
import { AuditSection } from "./AuditSection";

/** Engineering detail, kept out of the reading path: scope table and provenance. */
export function TechnicalSection({ record }: { record: ReportRecord }) {
  const content = record.report.report_json;
  return (
    <>
      <Notice tone="info">
        Phần này dành cho kỹ sư và chuyên viên muốn kiểm tra lại cách hệ thống ra kết quả: quy định
        nào được xét và vì sao, phiên bản kho tri thức và lần chạy đã dùng. Người đọc báo cáo thông
        thường không cần xem.
      </Notice>
      <ChecklistSection applicable={content.applicable_legal_scope} checklist={content.checklist} />
      <AuditSection record={record} />
    </>
  );
}
