import type { Recommendation } from "../../../shared/api/client";
import { Empty, Ids, Section, StatusBadge } from "../../../shared/components/ui";
import { LegalBasis } from "../../reports/legalBasis";
import { focusDomId, useReportNav } from "../../reports/nav";
import { useReportPresentation } from "../../reports/assessmentStatus";
import { cleanRecommendationText } from "../../../shared/text";

function formatModelVersion(code: string | null | undefined): string {
  if (!code) return "—";
  if (code === "TEMPLATE_ENGINE_NO_LLM") return "Quy tắc khuyến nghị chuẩn hóa (Playbook pháp lý)";
  if (code.startsWith("BACKEND_NUMERIC")) return "Đối soát định lượng số liệu";
  if (code.startsWith("BACKEND_SCOPE")) return "Kiểm tra phạm vi áp dụng";
  if (code.includes("GEMINI") || code.includes("OPENAI") || code.includes("LLM")) return "Trợ lý pháp lý AI";
  return code;
}

function RecommendationBody({ text }: { text: string }) {
  const cleaned = cleanRecommendationText(text);
  const lines = cleaned.split("\n");
  return (
    <div className="recommendation-content">
      {lines.map((line, i) => {
        const isHeading =
          line.startsWith("Thông tin cần làm rõ:") ||
          line.startsWith("Các nội dung cần đối chiếu/bổ sung:") ||
          line.startsWith("Nội dung tham chiếu để đối chiếu khi áp dụng:") ||
          line.startsWith("Dự thảo gợi ý:") ||
          line.startsWith("Bằng chứng cần lưu:") ||
          line.startsWith("Kiểm tra sau khắc phục:");
        if (isHeading) {
          const colonIdx = line.indexOf(":");
          const title = line.slice(0, colonIdx + 1);
          const body = line.slice(colonIdx + 1).trim();
          return (
            <p key={i} className="small" style={{ margin: "6px 0" }}>
              <strong>{title}</strong> {body}
            </p>
          );
        }
        if (line.startsWith("- ")) {
          return (
            <div key={i} className="small muted" style={{ paddingLeft: "16px", margin: "2px 0" }}>
              • {line.slice(2)}
            </div>
          );
        }
        return (
          <p key={i} style={{ margin: "6px 0", fontWeight: i === 0 ? 500 : 400 }}>
            {line}
          </p>
        );
      })}
    </div>
  );
}

/** Verification requests are kept apart from corrective actions for established findings. */
const VERIFICATION_ACTIONS = new Set([
  "VERIFY", "VERIFY_REFERENCE", "REQUEST_VERIFICATION", "REQUEST_EVIDENCE",
]);

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
  const presentation = useReportPresentation();
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
            <StatusBadge kind="actionType" code={r.loai_hanh_dong} />
            <StatusBadge kind="review" code={r.review_status} />
          </header>
          <RecommendationBody text={presentation?.recommendations[r.khuyen_nghi_ca_id]?.text ?? r.noi_dung} />
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
              <dt>Phương thức</dt>
              <dd>
                <span>{formatModelVersion(r.model_version)}</span>
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
