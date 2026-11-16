import type { ApplicableRequirement, ScopeResolution } from "../../../shared/api/client";
import { Empty, MachineText, Section, StatusBadge, Table } from "../../../shared/components/ui";
import { label } from "../../../shared/labels";
import { useReportNav } from "../../reports/nav";
import { formatRequirementId, formatVersionId, useReportIndex } from "../../reports/reportIndex";

const GROUP_NAMES: Record<string, string> = {
  NHAO: "Luật Nhà ở",
  CAN_HO_2024: "Chế độ Căn hộ 2024",
  MAU_CAN_HO: "Hợp đồng mẫu Căn hộ",
  KDBDS: "Luật Kinh doanh BĐS",
  ND_KDBDS: "Nghị định KDBĐS",
  VB_DS_2015: "Bộ luật Dân sự 2015",
  BVNTD: "Luật BVQL người tiêu dùng",
  BVQLNTD: "Luật BVQL người tiêu dùng",
  VB_TT_2010: "Luật Trọng tài thương mại",
  TTTM: "Luật Trọng tài thương mại",
  VBPL002: "Nghị định 55/2024 (BVNTD)",
  VBPL003: "Quyết định 07/2024 (HĐ Mẫu)",
};

function formatGroupName(group: string | null | undefined): string {
  if (!group) return "—";
  return GROUP_NAMES[group] ?? group;
}

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
      description="C04/C05 do Scope và Temporal Resolver chọn từ hồ sơ hợp đồng và snapshot tri thức đã pin, độc lập với các viện dẫn hợp đồng tự nêu."
    >
      <h3 className="subhead">Yêu cầu được xét ({applicable.length})</h3>
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
                      title={a.requirement_id}
                    >
                      {formatRequirementId(a.requirement_id)}
                    </button>
                  ) : (
                    <span title={a.requirement_id}>{formatRequirementId(a.requirement_id)}</span>
                  )}
                </td>
                <td>{formatGroupName(a.nhom_phien_ban)}</td>
                <td>
                  <StatusBadge kind="scope" code={a.scope_status} />
                </td>
                <td>
                  {a.applicability_status === "NOT_APPLICABLE" ? (
                    <span className="muted small">Không chọn phiên bản — không áp dụng</span>
                  ) : (
                    <>
                      <StatusBadge kind="version" code={a.version_status} />{" "}
                      <span className="small font-medium" title={a.requirement_version_id ?? ""}>
                        {formatVersionId(a.requirement_version_id)}
                      </span>
                      {a.version_status !== "RESOLVED" && a.requirement_version_id && (
                        <span className="small muted"> (ứng viên)</span>
                      )}
                    </>
                  )}
                </td>
                <td>
                  <StatusBadge kind="applicability" code={a.applicability_status} />
                </td>
                <td className="small" title={a.loai_moc ?? undefined}>
                  <span className="font-medium">{a.loai_moc ? label("anchor", a.loai_moc).text : "—"}</span>
                  {a.moc_ap_dung ? ` (${a.moc_ap_dung})` : ""}
                </td>
                <td className="small">
                  <MachineText text={a.reason?.summary || [...new Set(Object.values(a.reason ?? {}))].join(" · ") || "—"} />
                </td>
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
                  <span title={c.requirement_id}>{formatRequirementId(c.requirement_id)}</span>
                </td>
                <td>{formatGroupName(c.nhom_phien_ban)}</td>
                <td>
                  <StatusBadge kind="scope" code={c.scope_status} />
                </td>
                <td className="small">
                  <MachineText text={c.scope_reason} />
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Section>
  );
}
