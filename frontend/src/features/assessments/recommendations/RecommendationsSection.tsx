import type { Recommendation } from "../../../shared/api/client";
import { Empty, Ids, Section, StatusBadge } from "../../../shared/components/ui";
import { LegalBasis } from "../../reports/legalBasis";
import { focusDomId, useReportNav } from "../../reports/nav";

/** Verification requests are kept apart from corrective actions for established findings. */
const VERIFICATION_ACTIONS = new Set(["REQUEST_VERIFICATION", "REQUEST_EVIDENCE"]);

export function RecommendationsSection({
  recommendations,
}: {
  recommendations: Recommendation[];
}) {
  const corrective = recommendations.filter((r) => !VERIFICATION_ACTIONS.has(r.loai_hanh_dong));
  const verification = recommendations.filter((r) => VERIFICATION_ACTIONS.has(r.loai_hanh_dong));
  return (
    <Section
      title="Khuyến nghị"
      description="C11 sinh từ template theo rủi ro; nội dung chờ chuyên viên review."
    >
      <h3 className="subhead">Hành động khắc phục ({corrective.length})</h3>
      <List items={corrective} empty="Không có hành động khắc phục cho finding đã xác lập." />
      <h3 className="subhead">Yêu cầu xác minh / bổ sung hồ sơ ({verification.length})</h3>
      <List items={verification} empty="Không có yêu cầu xác minh." />
    </Section>
  );
}

function List({ items, empty }: { items: Recommendation[]; empty: string }) {
  const { focus, go } = useReportNav();
  if (items.length === 0) return <Empty>{empty}</Empty>;
  return (
    <div className="stack">
      {items.map((r) => (
        <article
          key={r.khuyen_nghi_ca_id}
          className={`card-flat${focus === r.khuyen_nghi_ca_id ? " focused" : ""}`}
          id={focusDomId(r.khuyen_nghi_ca_id)}
        >
          <header className="criterion-head">
            <StatusBadge kind="severity" code={r.uu_tien} />
            <code>{r.loai_hanh_dong}</code>
            <StatusBadge kind="review" code={r.review_status} />
          </header>
          <p>{r.noi_dung}</p>
          <dl className="fields compact">
            <div>
              <dt>Bằng chứng</dt>
              <dd>
                <Ids ids={r.evidence_ids} empty="không có" />
              </dd>
            </div>
            <div>
              <dt>Căn cứ</dt>
              <dd>
                <LegalBasis ids={r.legal_basis_ids} />
              </dd>
            </div>
            <div>
              <dt>Sinh bởi</dt>
              <dd>
                <code>{r.model_version}</code>
              </dd>
            </div>
          </dl>
          <div className="links">
            <button
              type="button"
              className="link"
              onClick={() => go("risks", r.ket_qua_rui_ro_id)}
            >
              Xem rủi ro gốc
            </button>
          </div>
        </article>
      ))}
    </div>
  );
}
