import { useSearchParams } from "react-router-dom";

import type {
  CriterionResult,
  ReportContent,
  RequirementResult,
} from "../../../shared/api/client";
import {
  Disclosure,
  Empty,
  MachineText,
  Notice,
  Quote,
  RequirementTitle,
  Section,
  StatusBadge,
} from "../../../shared/components/ui";
import { useInsufficientCauses } from "../../reports/causes";
import { RequirementDistribution } from "../../reports/distributions";
import {
  type Cause,
  CAUSES,
  concludedCount,
  aiSuggestion,
  explainCriterion,
  explainRequirement,
  viDate,
} from "../../reports/explain";
import { LegalBasis, legalSourceUrl } from "../../reports/legalBasis";
import { focusDomId, useReportNav } from "../../reports/nav";
import {
  criterionSnapshot,
  criterionText,
  requirementIdOf,
  requirementText,
  requirementVersion,
  riskTitle,
  useReportIndex,
  useRequirementGroup,
  useRequirementName,
} from "../../reports/reportIndex";
import { OTHER_TOPIC, topicOrder, topicTitle } from "../../reports/topics";
import { label } from "../../../shared/labels";
import { useOpenEvidence } from "../evidence/EvidenceViewer";
import { RecommendationBlock } from "../risks/RisksSection";

const GATE_LABELS: Record<string, string> = {
  scope_confirmed: "Đã xác nhận quy định có áp dụng",
  version_resolved: "Đã chọn được điều luật có hiệu lực",
  evidence_validated: "Trích dẫn khớp nguyên văn hợp đồng",
  source_verified: "Nguồn luật đã xác minh",
  coverage_complete: "Đã đọc đủ phần hợp đồng liên quan",
  absence_verified: "Đã xác minh hợp đồng thật sự thiếu nội dung",
  exceptions_resolved: "Đã xét các trường hợp ngoại lệ",
  evidence_conflict: "Bằng chứng mâu thuẫn nhau",
};

export function useRequirementReason() {
  const index = useReportIndex();
  return (r: RequirementResult) =>
    explainRequirement(
      r,
      index.applicableById.get(r.yeu_cau_ca_id),
      index.criteriaByRequirement.get(r.yeu_cau_ca_id) ?? [],
    );
}

const STATUS_ORDER = ["NON_COMPLIANT", "PARTIAL", "INSUFFICIENT", "COMPLIANT"];

/** Every requirement to check, grouped by topic so a reader can go through the contract area by area. */
export function TopicsSection({ content }: { content: ReportContent }) {
  const index = useReportIndex();
  const groupOf = useRequirementGroup();
  const reasonOf = useRequirementReason();
  const { focus } = useReportNav();
  const [params, setParams] = useSearchParams();
  const results = content.compliance.requirement_results;
  const causes = useInsufficientCauses(content);
  const selected = params.get("cause") as Cause | null;
  const shown = selected ? results.filter((r) => reasonOf(r).cause === selected) : results;
  const statuses = new Set(results.map((r) => r.status));
  // Requirements in scope without a stored result must show as "not run", never as compliant.
  const withoutResult = content.applicable_legal_scope.filter(
    (a) =>
      !index.requirementById.has(a.yeu_cau_ca_id) && a.applicability_status !== "NOT_APPLICABLE",
  );
  const groups = new Map<string, RequirementResult[]>();
  for (const r of shown) {
    const key = groupOf(requirementIdOf(index, r.yeu_cau_ca_id)) ?? OTHER_TOPIC;
    groups.set(key, [...(groups.get(key) ?? []), r]);
  }
  const ordered = [...groups].sort((a, b) => topicOrder(a[0]) - topicOrder(b[0]));
  const setCause = (cause: Cause | null) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("focus");
      if (cause) next.set("cause", cause);
      else next.delete("cause");
      return next;
    });

  return (
    <Section
      title="Kiểm tra theo chủ đề"
      description="Toàn bộ quy định pháp luật cần xét cho hợp đồng này, nhóm theo chủ đề. Mở một chủ đề rồi mở từng quy định để xem lý do, các điểm kiểm tra, đoạn hợp đồng làm bằng chứng và điều luật."
    >
      {results.length === 0 && <Empty>Chưa có kết quả cho lần chạy này.</Empty>}
      {statuses.size > 1 && <RequirementDistribution results={results} />}
      {causes.length > 0 && (
        <div className="filter-row" role="group" aria-label="Lọc theo lý do">
          <span className="muted small">Lọc theo lý do chưa kết luận:</span>
          <button
            type="button"
            className="button"
            aria-pressed={!selected}
            onClick={() => setCause(null)}
          >
            Tất cả ({results.length})
          </button>
          {causes.map(([cause, { count }]) => (
            <button
              key={cause}
              type="button"
              className="button"
              aria-pressed={selected === cause}
              onClick={() => setCause(cause)}
            >
              {CAUSES[cause].title} ({count})
            </button>
          ))}
        </div>
      )}
      <div className="stack">
        {ordered.map(([topic, items]) => {
          const counts = STATUS_ORDER.map(
            (code) => [code, items.filter((r) => r.status === code).length] as const,
          ).filter(([, n]) => n > 0);
          const containsFocus = items.some(
            (r) =>
              r.yeu_cau_ca_id === focus ||
              (index.criteriaByRequirement.get(r.yeu_cau_ca_id) ?? []).some(
                (c) => c.ket_qua_id === focus,
              ),
          );
          const flagged = items.some((r) => r.status === "NON_COMPLIANT" || r.status === "PARTIAL");
          return (
            <details
              key={topic}
              className="topic"
              open={containsFocus || flagged || !!selected || ordered.length === 1 || undefined}
            >
              <summary>
                <span className="topic-title">{topicTitle(topic)}</span>
                <span className="topic-counts">
                  {counts.map(([code, n]) => (
                    <span key={code} className={`badge tone-${label("requirement", code).tone}`}>
                      {n} {label("requirement", code).text.toLowerCase()}
                    </span>
                  ))}
                </span>
              </summary>
              <div className="stack">
                {items.map((r) => (
                  <RequirementCard key={r.tuan_thu_id} requirement={r} reason={reasonOf(r).text} />
                ))}
              </div>
            </details>
          );
        })}
      </div>
      {withoutResult.length > 0 && (
        <Notice tone="warn">
          {withoutResult.length} quy định có thể áp dụng nhưng chưa có kết quả đánh giá. Xem danh
          sách ở mục “Chi tiết kỹ thuật”.
        </Notice>
      )}
    </Section>
  );
}

export function RequirementCard({
  requirement,
  reason,
}: {
  requirement: RequirementResult;
  reason: string;
}) {
  const index = useReportIndex();
  const nameOf = useRequirementName();
  const { focus } = useReportNav();
  const criteria = index.criteriaByRequirement.get(requirement.yeu_cau_ca_id) ?? [];
  const requirementId = requirementIdOf(index, requirement.yeu_cau_ca_id);
  const containsFocus =
    focus === requirement.yeu_cau_ca_id || criteria.some((c) => c.ket_qua_id === focus);
  const version = requirementVersion(requirement);
  const name = nameOf(requirementId);

  return (
    <details
      className="card"
      id={focusDomId(requirement.yeu_cau_ca_id)}
      open={containsFocus || undefined}
    >
      <summary className="card-summary">
        <StatusBadge kind="requirement" code={requirement.status} />
        <span className="card-title">
          <RequirementTitle
            name={name ?? (version?.noi_dung ? requirementText(requirement) : null)}
            code={requirementId ?? requirement.yeu_cau_ca_id}
          />
        </span>
        <p className="reason-line">{reason}</p>
      </summary>
      <div className="card-body">
        {name &&
          typeof version?.noi_dung === "string" &&
          version.noi_dung.trim() !== name.trim() && <p>{version.noi_dung}</p>}
        <dl className="fields compact">
          <div>
            <dt>Căn cứ pháp lý</dt>
            <dd>
              <LegalBasis
                ids={[version?.source_van_ban_id, version?.dieu_khoan_id].filter(
                  (x): x is string => typeof x === "string",
                )}
              />{" "}
              {typeof version?.hieu_luc_tu === "string" && (
                <span className="muted small">hiệu lực từ {viDate(version.hieu_luc_tu)}</span>
              )}
              {!version && <span className="muted">chưa chọn được điều luật</span>}
            </dd>
          </div>
          <div>
            <dt>Điểm kiểm tra</dt>
            <dd>
              {requirement.so_tieu_chi_ap_dung === 0
                ? "Chưa có (quy định chưa được xác nhận áp dụng)"
                : `${requirement.so_tieu_chi_ap_dung} điểm: ${concludedCount(requirement)} có kết luận${
                    requirement.so_unknown > 0 ? `, ${requirement.so_unknown} chưa xác định` : ""
                  }`}
            </dd>
          </div>
        </dl>
        <h3 className="subhead">Điểm kiểm tra ({criteria.length})</h3>
        {criteria.length === 0 && (
          <Empty>Chưa có điểm kiểm tra nào vì quy định chưa được xác nhận áp dụng.</Empty>
        )}
        <div className="stack">
          {criteria.map((c) => (
            <CriterionCard key={c.ket_qua_id} criterion={c} />
          ))}
        </div>
      </div>
    </details>
  );
}

function CriterionCard({ criterion }: { criterion: CriterionResult }) {
  const index = useReportIndex();
  const { focus, go } = useReportNav();
  const openEvidence = useOpenEvidence();
  const risks = index.risksByCriterion.get(criterion.ket_qua_id) ?? [];
  const snapshot = criterionSnapshot(criterion);
  const basisText = typeof snapshot?.can_cu_cu_the === "string" ? snapshot.can_cu_cu_the : null;
  const basisUrl = legalSourceUrl(
    typeof snapshot?.url_can_cu === "string" ? snapshot.url_can_cu : null,
    basisText ?? "",
  );
  const gates = Object.entries(criterion.gates);
  const why = explainCriterion(criterion);

  return (
    <article
      className={`criterion${focus === criterion.ket_qua_id ? " focused" : ""}`}
      id={focusDomId(criterion.ket_qua_id)}
    >
      <header className="criterion-head">
        <StatusBadge kind="criterion" code={criterion.finding} />
        <strong>{criterionText(criterion)}</strong>
        {criterion.mandatory && <span className="tag">bắt buộc</span>}
        {criterion.excluded && <span className="tag">loại trừ: {criterion.exclusion_reason}</span>}
      </header>
      {why ? (
        <p className="uncertain">Vì sao chưa kết luận: {why}</p>
      ) : (
        <MachineText text={criterion.giai_thich} />
      )}
      <AiSuggestionNote reason={criterion.uncertainty_reason} />

      <h4 className="minihead">Bằng chứng trong hợp đồng</h4>
      {criterion.evidence?.length ? (
        criterion.evidence.map((e, i) => (
          <Quote
            key={`${e.doan_id}-${i}`}
            text={e.trich_dan}
            chunkId={e.doan_id}
            start={e.ky_tu_bat_dau}
            end={e.ky_tu_ket_thuc}
            onOpen={
              openEvidence
                ? () =>
                    openEvidence({
                      doanId: e.doan_id,
                      start: e.ky_tu_bat_dau,
                      end: e.ky_tu_ket_thuc,
                      quote: e.trich_dan,
                    })
                : undefined
            }
          />
        ))
      ) : (
        <Empty>
          Chưa chọn được đoạn hợp đồng nào làm bằng chứng. Điều này không có nghĩa là hợp đồng thiếu
          nội dung.
        </Empty>
      )}
      {criterion.external_evidence?.map((e) => (
        <p key={e.bang_chung_id} className="small">
          Chứng từ ngoài <code>{e.bang_chung_id}</code> {e.verified ? "(đã xác minh)" : "(chưa xác minh)"}
        </p>
      ))}

      <dl className="fields compact">
        <div>
          <dt>Căn cứ pháp lý</dt>
          <dd>
            <LegalBasis ids={criterion.legal_basis_ids} />
            {basisText && <span className="small"> {basisText}</span>}{" "}
            {basisUrl && (
              <a href={basisUrl} target="_blank" rel="noreferrer">
                xem văn bản
              </a>
            )}
          </dd>
        </div>
        <div>
          <dt>Người duyệt</dt>
          <dd>
            <StatusBadge kind="review" code={criterion.review_status} />
          </dd>
        </div>
      </dl>

      {/* "To verify" items are this criterion's to-do: show what to do right here. */}
      {risks
        .filter((r) => r.risk_type === "VERIFICATION")
        .flatMap((r) => index.recommendationsByRisk.get(r.ket_qua_rui_ro_id) ?? [])
        .map((k) => (
          <RecommendationBlock key={k.khuyen_nghi_ca_id} recommendation={k} />
        ))}
      {risks.some((r) => r.risk_type !== "VERIFICATION") && (
        <div className="links">
          Rủi ro:{" "}
          {risks
            .filter((r) => r.risk_type !== "VERIFICATION")
            .map((r) => (
              <button
                key={r.ket_qua_rui_ro_id}
                type="button"
                className="link"
                onClick={() => go("risks", r.ket_qua_rui_ro_id)}
              >
                {riskTitle(r)}
              </button>
            ))}
        </div>
      )}

      <Disclosure summary="Các điều kiện hệ thống đã kiểm tra">
        <p className="small muted">
          Kết luận chỉ được chấp nhận khi đủ các điều kiện dưới đây. ✗ là điều kiện còn thiếu.
        </p>
        <div className="gates" aria-label="Điều kiện kiểm tra">
          {gates.map(([gate, ok]) => {
            // A conflict flag is "good" when false, every other gate when true.
            const good = gate === "evidence_conflict" ? !ok : ok;
            return (
              <span key={gate} className={`gate ${good ? "ok" : "no"}`}>
                {good ? "✓" : "✗"} {GATE_LABELS[gate] ?? gate}
              </span>
            );
          })}
        </div>
        <p className="small muted">
          {criterion.model_version === "NO_LLM_CALL"
            ? "Điểm này chưa được AI đọc."
            : `Đã được AI đọc (${criterion.model_version}).`}
        </p>
      </Disclosure>
    </article>
  );
}

/** The AI's own conclusion when the backend did not accept it: a hint, clearly labelled. */
export function AiSuggestionNote({ reason }: { reason: string | null | undefined }) {
  const hint = aiSuggestion(reason);
  if (!hint) return null;
  return (
    <p className="ai-suggestion">
      <strong>Gợi ý của AI, chưa được chấp nhận:</strong> {label("criterion", hint.finding).text}.{" "}
      {hint.text} <span className="muted">Chuyên viên xác nhận hoặc sửa ở mục Rà soát.</span>
    </p>
  );
}
