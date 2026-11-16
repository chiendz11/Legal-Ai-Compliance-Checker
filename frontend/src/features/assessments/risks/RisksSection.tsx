import type { Recommendation, RiskResult } from "../../../shared/api/client";
import { StatusBadge } from "../../../shared/components/ui";
import { shortCitationId } from "../../../shared/labels";
import { useReportPresentation } from "../../reports/assessmentStatus";
import { LegalBasis } from "../../reports/legalBasis";
import { focusDomId, useReportNav } from "../../reports/nav";
import { readRecommendation } from "../../reports/recommendation";
import { criterionText, riskTitle, useReportIndex } from "../../reports/reportIndex";

// Actions that ask for a check, not a change to the contract (docs/contracts/integration_policy.json).
const VERIFICATION_ACTIONS = new Set([
  "VERIFY", "VERIFY_REFERENCE", "REQUEST_VERIFICATION", "REQUEST_EVIDENCE",
]);

function actionLabel(code: string): string {
  if (code === "REQUEST_EVIDENCE") return "Cần bổ sung chứng cứ";
  return VERIFICATION_ACTIONS.has(code) ? "Cần xác minh" : "Cách sửa";
}

/** One line saying what to do; the template's full text stays one click away. */
export function RecommendationBlock({ recommendation }: { recommendation: Recommendation }) {
  const { focus } = useReportNav();
  // The report's presentation binds draft slots to observed values and withholds a draft whose
  // values are missing; the stored template text is only a fallback for older reports.
  const presentation = useReportPresentation();
  const text =
    presentation?.recommendations[recommendation.khuyen_nghi_ca_id]?.text ?? recommendation.noi_dung;
  const view = readRecommendation(text);
  return (
    <div
      className={`recommendation${focus === recommendation.khuyen_nghi_ca_id ? " focused" : ""}`}
      id={focusDomId(recommendation.khuyen_nghi_ca_id)}
    >
      <span className="recommendation-label">
        {actionLabel(recommendation.loai_hanh_dong)}
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
          <button
            type="button"
            className="link"
            onClick={() => go("citations", finding.finding_id)}
            title={finding.vien_dan_id}
          >
            Xem {shortCitationId(finding.vien_dan_id)} (
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

