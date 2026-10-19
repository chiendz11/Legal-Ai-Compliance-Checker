import type { Recommendation, ReportContent, RiskResult } from "../../../shared/api/client";
import { Empty, Ids, Section, StatusBadge } from "../../../shared/components/ui";
import { focusDomId, useReportNav } from "../../reports/nav";
import { criterionText, riskTitle, useReportIndex } from "../../reports/reportIndex";

const GROUPS = [
  { key: "compliance", title: "Rủi ro tuân thủ", note: "Phát sinh từ kết quả tiêu chí (C07)." },
  { key: "citation", title: "Rủi ro viện dẫn", note: "Phát sinh từ xác minh viện dẫn (C09)." },
  {
    key: "verification",
    title: "Cần xác minh",
    note: "Chưa đủ căn cứ để kết luận; cần bổ sung hồ sơ hoặc review.",
  },
] as const;

export function RisksSection({
  risks,
  recommendations,
}: {
  risks: ReportContent["risks"];
  recommendations: Recommendation[];
}) {
  const { focus } = useReportNav();
  const recoByRisk = new Map<string, Recommendation[]>();
  for (const r of recommendations) {
    recoByRisk.set(r.ket_qua_rui_ro_id, [...(recoByRisk.get(r.ket_qua_rui_ro_id) ?? []), r]);
  }
  return (
    <Section
      title="Rủi ro"
      description="C10 tách theo nguồn. Mức độ do Risk Engine cung cấp; mỗi rủi ro trỏ về finding gốc."
    >
      {GROUPS.map((group) => {
        const items = risks[group.key];
        const containsFocus = items.some((r) => r.ket_qua_rui_ro_id === focus);
        return (
          <details
            key={group.key}
            className="group"
            open={containsFocus || (group.key !== "verification" && items.length > 0) || undefined}
          >
            <summary>
              <strong>{group.title}</strong> <span className="count">{items.length}</span>
              <span className="muted small"> {group.note}</span>
            </summary>
            {items.length === 0 ? (
              <Empty>Không có.</Empty>
            ) : (
              <div className="stack">
                {items.map((r) => (
                  <RiskCard
                    key={r.ket_qua_rui_ro_id}
                    risk={r}
                    recommendations={recoByRisk.get(r.ket_qua_rui_ro_id) ?? []}
                  />
                ))}
              </div>
            )}
          </details>
        );
      })}
    </Section>
  );
}

function RiskCard({
  risk,
  recommendations,
}: {
  risk: RiskResult;
  recommendations: Recommendation[];
}) {
  const index = useReportIndex();
  const { focus, go } = useReportNav();
  const criterion = risk.source.ket_qua_tieu_chi_id
    ? index.criterionById.get(risk.source.ket_qua_tieu_chi_id)
    : undefined;
  const finding = risk.source.citation_finding_id
    ? index.findingById.get(risk.source.citation_finding_id)
    : undefined;
  return (
    <article
      className={`card-flat${focus === risk.ket_qua_rui_ro_id ? " focused" : ""}`}
      id={focusDomId(risk.ket_qua_rui_ro_id)}
    >
      <header className="criterion-head">
        <StatusBadge kind="severity" code={risk.severity} />
        <StatusBadge kind="riskType" code={risk.risk_type} />
        <strong>{riskTitle(risk)}</strong>
      </header>
      <p>{risk.giai_thich}</p>
      <div className="links">
        Nguồn:{" "}
        {criterion && (
          <button type="button" className="link" onClick={() => go("compliance", criterion.ket_qua_id)}>
            Tiêu chí: {criterionText(criterion)} (
            <StatusBadge kind="criterion" code={criterion.finding} />)
          </button>
        )}
        {finding && (
          <button type="button" className="link" onClick={() => go("citations", finding.finding_id)}>
            Viện dẫn <code>{finding.vien_dan_id}</code> (
            <StatusBadge kind="citation" code={finding.status} />)
          </button>
        )}
        {!criterion && !finding && (
          <span className="uncertain">Không tìm thấy finding nguồn trong report.</span>
        )}
      </div>
      <dl className="fields compact">
        <div>
          <dt>Quy tắc</dt>
          <dd>
            <code>{risk.quy_tac_id}</code>
          </dd>
        </div>
        <div>
          <dt>Căn cứ</dt>
          <dd>
            <Ids ids={risk.legal_basis_ids} />
          </dd>
        </div>
        <div>
          <dt>Review</dt>
          <dd>
            <StatusBadge kind="review" code={risk.review_status} />
          </dd>
        </div>
      </dl>
      {recommendations.length > 0 && (
        <div className="links">
          Khuyến nghị:{" "}
          {recommendations.map((k) => (
            <button
              key={k.khuyen_nghi_ca_id}
              type="button"
              className="link"
              onClick={() => go("recommendations", k.khuyen_nghi_ca_id)}
            >
              {k.loai_hanh_dong}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
