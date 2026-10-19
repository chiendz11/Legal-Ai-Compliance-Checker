import type { ApplicableRequirement, ScopeResolution } from "../../../shared/api/client";
import { Empty, Section, StatusBadge, Table } from "../../../shared/components/ui";
import { useReportNav } from "../../reports/nav";
import { useReportIndex } from "../../reports/reportIndex";

export function ChecklistSection({
  applicable,
  checklist,
}: {
  applicable: ApplicableRequirement[];
  checklist: ScopeResolution[];
}) {
  const index = useReportIndex();
  const { go } = useReportNav();
  return (
    <Section
      title="Phạm vi pháp lý và checklist"
      description="C04/C05 do Scope và Temporal Resolver chọn từ hồ sơ hợp đồng và Gold Legal DB, độc lập với các viện dẫn hợp đồng tự nêu."
    >
      <h3 className="subhead">Yêu cầu áp dụng ({applicable.length})</h3>
      {applicable.length === 0 ? (
        <Empty>Chưa có yêu cầu áp dụng.</Empty>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>Yêu cầu</th>
              <th>Nhóm</th>
              <th>Phạm vi</th>
              <th>Phiên bản</th>
              <th>Áp dụng</th>
              <th>Mốc</th>
              <th>Lý do</th>
            </tr>
          </thead>
          <tbody>
            {applicable.map((a) => (
              <tr key={a.yeu_cau_ca_id}>
                <td>
                  {index.requirementById.has(a.yeu_cau_ca_id) ? (
                    <button
                      type="button"
                      className="link"
                      onClick={() => go("compliance", a.yeu_cau_ca_id)}
                    >
                      {a.requirement_id}
                    </button>
                  ) : (
                    <code>{a.requirement_id}</code>
                  )}
                </td>
                <td>{a.nhom_phien_ban ?? "—"}</td>
                <td>
                  <StatusBadge kind="scope" code={a.scope_status} />
                </td>
                <td>
                  <StatusBadge kind="version" code={a.version_status} />{" "}
                  <code className="small">{a.requirement_version_id ?? ""}</code>
                </td>
                <td>
                  <StatusBadge kind="applicability" code={a.applicability_status} />
                </td>
                <td className="small">
                  {a.loai_moc ?? "—"} {a.moc_ap_dung ?? ""}
                </td>
                <td className="small">{Object.values(a.reason ?? {}).join(" · ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      <h3 className="subhead">Checklist phạm vi ({checklist.length})</h3>
      {checklist.length === 0 ? (
        <Empty>Chưa có checklist.</Empty>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>Yêu cầu</th>
              <th>Nhóm</th>
              <th>Phạm vi</th>
              <th>Lý do phạm vi</th>
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
    </Section>
  );
}
