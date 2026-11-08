import type { Recommendation, RiskResult } from "../../../shared/api/client";
import { StatusBadge } from "../../../shared/components/ui";
import { LegalBasis } from "../../reports/legalBasis";
import { focusDomId, useReportNav } from "../../reports/nav";
import { readRecommendation } from "../../reports/recommendation";
import { criterionText, riskTitle, useReportIndex } from "../../reports/reportIndex";

const ACTION_LABELS: Record<string, string> = {
  REQUEST_VERIFICATION: "Việc cần làm",
  REQUEST_EVIDENCE: "Cần bổ sung chứng cứ",
};


/** One line saying what to do; the template's full text stays one click away. */
export function RecommendationBlock({ recommendation }: { recommendation: Recommendation }) {
  const { focus } = useReportNav();
  const view = readRecommendation(recommendation.noi_dung);
  return (
    <div
      className={`recommendation${focus === recommendation.khuyen_nghi_ca_id ? " focused" : ""}`}
      id={focusDomId(recommendation.khuyen_nghi_ca_id)}
    >
      <span className="recommendation-label">
        {ACTION_LABELS[recommendation.loai_hanh_dong] ?? "Việc cần làm"}
      </span>
      <p>{view.action}</p>
      {view.details.length > 0 && (
        <details className="more-filters">
          <summary>Xem gợi ý đầy đủ</summary>
          <dl className="recommendation-details">
            {view.details.map((d) => (
              <div key={d.title}>
                <dt>{d.title}</dt>
                <dd>{d.text}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </div>
  );
}

export function RiskCard({
  risk,
  recommendations,
  compact = false,
}: {
  risk: RiskResult;
  recommendations: Recommendation[];
  compact?: boolean;
}) {
  const index = useReportIndex();
  const { focus, go } = useReportNav();
  const criterion = risk.source.ket_qua_tieu_chi_id
    ? index.criterionById.get(risk.source.ket_qua_tieu_chi_id)
    : undefined;
  const finding = risk.source.citation_finding_id
    ? index.findingById.get(risk.source.citation_finding_id)
    : undefined;
  const snapshot = risk.risk_snapshot as { mo_ta?: string };
  return (
    <article
      className={`card-flat risk${focus === risk.ket_qua_rui_ro_id ? " focused" : ""}`}
      id={focusDomId(risk.ket_qua_rui_ro_id)}
    >
      <header className="criterion-head">
        {risk.severity !== "REVIEW_REQUIRED" && <StatusBadge kind="severity" code={risk.severity} />}
        <strong>{riskTitle(risk)}</strong>
      </header>
      {!compact && snapshot.mo_ta && <p>{snapshot.mo_ta}</p>}
      {recommendations.map((k) => (
        <RecommendationBlock key={k.khuyen_nghi_ca_id} recommendation={k} />
      ))}
      <div className="links">
        {criterion && (
          <button type="button" className="link" onClick={() => go("topics", criterion.ket_qua_id)}>
            Xem điểm kiểm tra: {criterionText(criterion)}
          </button>
        )}
        {finding && (
          <button type="button" className="link" onClick={() => go("citations", finding.finding_id)}>
            Xem trích dẫn <code>{finding.vien_dan_id}</code> (
            <StatusBadge kind="citation" code={finding.status} />)
          </button>
        )}
      </div>
      {risk.legal_basis_ids.length > 0 && (
        <p className="small">
          <span className="muted">Căn cứ pháp lý: </span>
          <LegalBasis ids={risk.legal_basis_ids} />
        </p>
      )}
    </article>
  );
}

