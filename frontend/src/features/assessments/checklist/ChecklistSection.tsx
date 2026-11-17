import { useState } from "react";

import type { ApplicableRequirement, ScopeResolution } from "../../../shared/api/client";
import {
  Disclosure,
  Empty,
  RequirementTitle,
  Section,
  StatusBadge,
  Table,
} from "../../../shared/components/ui";
import { label } from "../../../shared/labels";
import { explainApplicable, viDate } from "../../reports/explain";
import { useReportNav } from "../../reports/nav";
import { useReportIndex, useRequirementName } from "../../reports/reportIndex";

export function ChecklistSection({
  applicable,
  checklist,
}: {
  applicable: ApplicableRequirement[];
  checklist: ScopeResolution[];
}) {
  const [showAll, setShowAll] = useState(false);
  const notApplicable = applicable.filter((a) => a.applicability_status === "NOT_APPLICABLE");
  // Rows that matter for this contract come first; "does not apply" ones are hidden by default.
  const rows = showAll
    ? applicable
    : applicable.filter((a) => a.applicability_status !== "NOT_APPLICABLE");
  return (
    <Section
      title="Quy định pháp luật áp dụng"
      description="Hệ thống đối chiếu hợp đồng với toàn bộ quy định trong kho tri thức pháp lý để biết quy định nào áp dụng, dựa trên thông tin đọc được từ hợp đồng (loại hợp đồng, các bên, ngày ký…). Danh sách này không phụ thuộc vào các luật mà chính hợp đồng trích dẫn."
    >
      <div className="filter-row">
        <span className="muted small">
          Đang hiện {rows.length}/{applicable.length} quy định.
        </span>
        {notApplicable.length > 0 && (
          <button
            type="button"
            className="button"
            aria-pressed={showAll}
            onClick={() => setShowAll(!showAll)}
          >
            {showAll
              ? `Ẩn ${notApplicable.length} quy định không áp dụng`
              : `Hiện thêm ${notApplicable.length} quy định không áp dụng`}
          </button>
        )}
      </div>
      {rows.length === 0 ? (
        <Empty>Không có quy định nào cần xét.</Empty>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>Quy định</th>
              <th>Có áp dụng?</th>
              <th>Mốc thời gian</th>
              <th>Giải thích</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <Row key={a.yeu_cau_ca_id} requirement={a} />
            ))}
          </tbody>
        </Table>
      )}

      <Disclosure summary="Chi tiết kỹ thuật: bảng xác định phạm vi (dành cho kỹ sư)">
        {checklist.length === 0 ? (
          <Empty>Chưa có checklist.</Empty>
        ) : (
          <Table>
            <thead>
              <tr>
                <th>Mã</th>
                <th>Nhóm</th>
                <th>Phạm vi</th>
                <th>Lý do (nguyên văn module)</th>
              </tr>
            </thead>
            <tbody>
              {checklist.map((c) => (
                <tr key={c.yeu_cau_ca_id}>
                  <td>
                    <code>{c.requirement_id}</code>
                  </td>
                  <td>{c.nhom_phien_ban ?? "—"}</td>
                  <td>
                    <StatusBadge kind="scope" code={c.scope_status} />
                  </td>
                  <td className="small">{c.scope_reason}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Disclosure>
    </Section>
  );
}

function Row({ requirement: a }: { requirement: ApplicableRequirement }) {
  const index = useReportIndex();
  const nameOf = useRequirementName();
  const { go } = useReportNav();
  const reason = a.reason ?? {};
  const trace = reason.summary || [...new Set(Object.values(reason))].join(" · ") || "—";
  const title = <RequirementTitle name={nameOf(a.requirement_id)} code={a.requirement_id} />;
  return (
    <tr>
      <td>
        {index.requirementById.has(a.yeu_cau_ca_id) ? (
          <button type="button" className="link" onClick={() => go("compliance", a.yeu_cau_ca_id)}>
            {title}
          </button>
        ) : (
          title
        )}
      </td>
      <td>
        <StatusBadge kind="applicability" code={a.applicability_status} />
      </td>
      <td className="small">
        {a.loai_moc ? label("markerType", a.loai_moc).text : "—"}
        {a.moc_ap_dung ? ` ${viDate(a.moc_ap_dung)}` : ""}
      </td>
      <td className="small reason-cell">
        {explainApplicable(a).text}
        <details className="machine-note">
          <summary>Chi tiết kỹ thuật</summary>
          <p>
            <StatusBadge kind="scope" code={a.scope_status} />{" "}
            {a.applicability_status === "NOT_APPLICABLE" && !a.requirement_version_id ? (
              "Không chọn phiên bản vì không áp dụng"
            ) : (
              <>
                <StatusBadge kind="version" code={a.version_status} />{" "}
                <code>{a.requirement_version_id ?? ""}</code>
                {a.version_status !== "RESOLVED" && a.requirement_version_id && " (ứng viên)"}
              </>
            )}
          </p>
          <p>{trace}</p>
        </details>
      </td>
    </tr>
  );
}
