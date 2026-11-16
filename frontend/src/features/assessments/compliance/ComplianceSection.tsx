import { requirementDisplayStatus, criterionDisplayStatus, useReportPresentation } from "../../reports/assessmentStatus";
import type {
  CriterionResult,
  ReportContent,
  RequirementResult,
} from "../../../shared/api/client";
import {
  Empty,
  Ids,
  MachineText,
  Notice,
  Quote,
  Section,
  StatusBadge,
} from "../../../shared/components/ui";
import { RequirementDistribution } from "../../reports/distributions";
import { LegalBasis } from "../../reports/legalBasis";
import { focusDomId, useReportNav } from "../../reports/nav";
import { cleanExplanationText } from "../../../shared/text";
import { useOpenEvidence } from "../evidence/EvidenceViewer";
import {
  criterionText,
  requirementText,
  riskTitle,
  useReportIndex,
} from "../../reports/reportIndex";

const GATE_LABELS: Record<string, string> = {
  scope_confirmed: "Phạm vi đã xác nhận",
  version_resolved: "Đã chọn phiên bản",
  evidence_validated: "Bằng chứng hợp lệ",
  source_verified: "Nguồn đã xác minh",
  coverage_complete: "Đã xác nhận độ phủ bằng chứng toàn văn",
  absence_verified: "Đã xác minh vắng nội dung",
  exceptions_resolved: "Đã xét ngoại lệ",
  evidence_conflict: "Bằng chứng mâu thuẫn",
};

export function ComplianceSection({ content }: { content: ReportContent }) {
  const index = useReportIndex();
  const results = content.compliance.requirement_results;
  const notTriggered = results.filter((r) => r.requirement_snapshot_json.assessment_disposition === "NOT_TRIGGERED");
  const outsideScope = results.filter((r) => r.requirement_snapshot_json.assessment_disposition === "OUTSIDE_REVIEW_SCOPE");
  // Requirements in scope without a stored result must show as "not run", never as compliant;
  // NOT_APPLICABLE ones were excluded on purpose and are listed separately.
  const unresolved = content.applicable_legal_scope.filter(
    (a) => !index.requirementById.has(a.yeu_cau_ca_id),
  );
  const excluded = unresolved.filter((a) => a.applicability_status === "NOT_APPLICABLE");
  const withoutResult = unresolved.filter((a) => a.applicability_status !== "NOT_APPLICABLE");
  return (
    <Section
      title="Kết quả tuân thủ"
      description="C08 theo yêu cầu, mở từng yêu cầu để xem C07 theo tiêu chí, bằng chứng và căn cứ. Trạng thái do backend tổng hợp."
    >
      {results.length === 0 && <Empty>Chưa có kết quả tuân thủ cho run này.</Empty>}
      {results.length > 0 && <RequirementDistribution results={results} />}
      {results.some((r) => r.requirement_snapshot_json?.conclusion_scope === "CONTRACT_CONTENT_ONLY") && (
        <Notice tone="info">
          <strong>Phạm vi rà soát: Dự thảo hợp đồng</strong> — Hệ thống thẩm định câu chữ và điều khoản thỏa thuận trên văn bản dự thảo trước khi ký. Các nghĩa vụ cần chứng từ thực tế ngoài đời được phân loại riêng.
        </Notice>
      )}
      {outsideScope.length > 0 && <Notice tone="info">
        {outsideScope.length} yêu cầu nằm ngoài phạm vi rà soát dự thảo đã chọn.
        Các nghĩa vụ này chưa được đánh giá, không được coi là tuân thủ hoặc không áp dụng pháp luật.
      </Notice>}
      {notTriggered.length > 0 && <Notice tone="info">
        {notTriggered.length} yêu cầu không phát sinh điều kiện đánh giá trong lần này:
        các tiêu chí bắt buộc đã được loại trừ có căn cứ. Nhóm này không phải thiếu
        hồ sơ; trạng thái C08 vẫn được giữ theo policy tổng hợp đã pin.
      </Notice>}
      <div className="stack">
        {results.map((r) => (
          <RequirementCard key={r.tuan_thu_id} requirement={r} />
        ))}
      </div>
      {withoutResult.length > 0 && (
        <Notice tone="warn">
          {withoutResult.length} yêu cầu trong phạm vi chưa có kết quả:{" "}
          <Ids ids={withoutResult.map((a) => a.yeu_cau_ca_id)} />
        </Notice>
      )}
      {excluded.length > 0 && (
        <p className="muted small">
          Không đánh giá vì không áp dụng (NOT_APPLICABLE):{" "}
          <Ids ids={excluded.map((a) => a.yeu_cau_ca_id)} />
        </p>
      )}
    </Section>
  );
}

function RequirementCard({ requirement }: { requirement: RequirementResult }) {
  const presentation = useReportPresentation();
  const view = presentation?.requirements[requirement.tuan_thu_id];
  const index = useReportIndex();
  const { focus } = useReportNav();
  const criteria = index.criteriaByRequirement.get(requirement.yeu_cau_ca_id) ?? [];
  const applicable = index.applicableById.get(requirement.yeu_cau_ca_id);
  const containsFocus =
    focus === requirement.yeu_cau_ca_id || criteria.some((c) => c.ket_qua_id === focus);
  const version = (requirement.requirement_snapshot_json as { version?: Record<string, unknown> })
    .version;
  const disposition = requirement.requirement_snapshot_json.assessment_disposition;

  return (
    <details
      className="card"
      id={focusDomId(requirement.yeu_cau_ca_id)}
      open={containsFocus || undefined}
    >
      <summary className="card-summary">
        <StatusBadge kind="requirement" code={view?.display_status ?? requirementDisplayStatus(requirement)} />
        {disposition === "NOT_TRIGGERED" && <span className="tag">Không phát sinh điều kiện</span>}
        <span className="card-title">{requirementText(requirement)}</span>
        <span className="muted small">
          {disposition === "OUTSIDE_REVIEW_SCOPE" ? "Không đánh giá trong phạm vi đã chọn" : <>
          Đã thẩm định {requirement.so_tieu_chi_da_danh_gia}/{requirement.so_tieu_chi_ap_dung} tiêu
          chí{requirement.so_unknown > 0 ? ` · ${requirement.so_unknown} chưa xác định` : ""}
          </>}
        </span>
      </summary>
      <div className="card-body">
        {view?.coverage && <p className="small">{view.coverage.explanation}</p>}
        {disposition === "OUTSIDE_REVIEW_SCOPE" && <Notice tone="info">
          Chưa đánh giá việc giao kết, thực hiện hoặc chứng từ bên ngoài trong chế độ dự thảo.
          C08 gốc vẫn được lưu; đây là giới hạn phạm vi rà soát, không phải kết luận pháp lý.
        </Notice>}
        {disposition === "NOT_TRIGGERED" && <Notice tone="info">
          Không có tiêu chí bắt buộc còn áp dụng sau khi kiểm tra điều kiện riêng.
          Trạng thái C08 gốc: {requirement.status} theo policy đã pin; kết quả trình bày: không phát sinh nghĩa vụ.
        </Notice>}
        <MachineText text={requirement.giai_thich} />
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
                <span className="muted small">hiệu lực từ {version.hieu_luc_tu}</span>
              )}
            </dd>
          </div>
          <div>
            <dt>Trạng thái áp dụng</dt>
            <dd>
              <StatusBadge kind="version" code={applicable?.version_status} />{" "}
              <StatusBadge kind="applicability" code={applicable?.applicability_status} />
            </dd>
          </div>
        </dl>
        <details className="small muted" style={{ margin: "8px 0" }}>
          <summary style={{ cursor: "pointer" }}>Chi tiết mã hệ thống (Yêu cầu & Quy tắc)</summary>
          <p style={{ marginTop: "4px", fontSize: "0.85em" }}>
            <code>Mã yêu cầu: {requirement.yeu_cau_ca_id}</code> | <code>Phiên bản: {applicable?.requirement_version_id ?? "chưa rõ"}</code> | <code>Mã quy tắc: {requirement.rule_version}</code>
          </p>
        </details>
        <h3 className="subhead">Tiêu chí ({criteria.length})</h3>
        {criteria.length === 0 && <Empty>Không có kết quả tiêu chí.</Empty>}
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
  const presentation = useReportPresentation();
  const view = presentation?.criteria[criterion.ket_qua_id];
  const risks = index.risksByCriterion.get(criterion.ket_qua_id) ?? [];
  const snapshot = (criterion.tieu_chi_snapshot_json as { criterion?: Record<string, unknown> })
    .criterion;
  const basisText = typeof snapshot?.can_cu_cu_the === "string" ? snapshot.can_cu_cu_the : null;
  const basisUrl = typeof snapshot?.url_can_cu === "string" ? snapshot.url_can_cu : null;
  const gates = Object.entries(criterion.gates);
  const displayText = view?.explanation ?? cleanExplanationText(criterion.giai_thich);

  return (
    <article
      className={`criterion${focus === criterion.ket_qua_id ? " focused" : ""}`}
      id={focusDomId(criterion.ket_qua_id)}
    >
      <header className="criterion-head">
        <StatusBadge kind="criterion" code={criterionDisplayStatus(criterion)} />
        <strong>{criterionText(criterion)}</strong>
        {criterion.mandatory && <span className="tag">bắt buộc</span>}
        {criterion.excluded && <span className="tag">loại trừ: {criterion.exclusion_reason}</span>}
      </header>
      <MachineText text={displayText} />
      {view?.audit_trace && view.audit_trace.length > 0 ? (
        <details className="small muted" style={{ margin: "6px 0" }}>
          <summary style={{ cursor: "pointer" }}>Dữ liệu kiểm toán kỹ thuật (Audit trace)</summary>
          <ul style={{ margin: "4px 0", paddingLeft: "1.2rem", fontSize: "0.85em" }}>
            {view.audit_trace.map((trace, idx) => (
              <li key={idx}><code>{trace}</code></li>
            ))}
          </ul>
        </details>
      ) : (
        criterion.uncertainty_reason && !criterion.giai_thich?.includes(criterion.uncertainty_reason) && (
          <p className="uncertain">Ghi chú xác minh: {cleanExplanationText(criterion.uncertainty_reason)}</p>
        )
      )}

      <p className="small muted">
        Các cờ dưới đây ghi nhận những kiểm tra đã thực hiện. Độ phủ toàn văn và xác minh
        vắng nội dung là thông tin riêng; chúng không phải điều kiện chung cho mọi kết luận.
        Kết luận thiếu nội dung vẫn cần đủ bằng chứng xác nhận việc vắng nội dung.
      </p>
      <div className="gates" aria-label="Điều kiện kiểm tra">
        {gates.map(([gate, ok]) => {
          // A conflict flag is "good" when false, every other gate when true.
          const good = gate === "evidence_conflict" ? !ok : ok;
          const informational = !ok && (gate === "coverage_complete" || gate === "absence_verified");
          return (
            <span key={gate} className={`gate ${informational ? "" : good ? "ok" : "no"}`}>
              {informational ? (gate === "coverage_complete"
                ? "○ Chưa xác nhận độ phủ bằng chứng toàn văn"
                : "○ Chưa xác minh vắng nội dung")
                : `${good ? "✓" : "✗"} ${GATE_LABELS[gate] ?? gate}`}
            </span>
          );
        })}
      </div>

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
      ) : criterion.external_evidence?.length ? (
        <Notice tone="info">
          Kết quả dùng chứng từ hoặc biên bản rà soát được liệt kê bên dưới.
          Không có trích đoạn hợp đồng đi kèm kết quả này.
        </Notice>
      ) : (
        <Empty>Chưa có bằng chứng được chọn (truy xuất rỗng, không đồng nghĩa với “Thiếu nội dung”).</Empty>
      )}
      {criterion.external_evidence?.map((e) => (
        <p key={e.bang_chung_id} className="small">
          {e.bang_chung_id.startsWith("DOCREVIEW_")
            ? "Biên bản rà soát toàn văn của máy"
            : e.bang_chung_id.startsWith("SYNTHETIC_") ? "Chứng từ giả lập" : "Chứng từ ngoài"}
          {" "}<code>{e.bang_chung_id}</code>{" "}
          {e.verified ? "(backend đã kiểm tra nguồn/hash)" : "(chưa kiểm tra nguồn)"}
        </p>
      ))}

      <dl className="fields compact">
        <div>
          <dt>Căn cứ hệ thống</dt>
          <dd>
            <LegalBasis ids={criterion.legal_basis_ids} />
            {basisText && <span className="small"> {basisText}</span>}{" "}
            {basisUrl && (
              <a href={basisUrl} target="_blank" rel="noreferrer">
                nguồn
              </a>
            )}
          </dd>
        </div>
        <div>
          <dt>Thẩm định</dt>
          <dd>
            <StatusBadge kind="review" code={criterion.review_status} />
          </dd>
        </div>
      </dl>
      <details className="small muted" style={{ marginTop: "6px" }}>
        <summary style={{ cursor: "pointer" }}>Thông số kỹ thuật tiêu chí</summary>
        <p style={{ marginTop: "4px", fontSize: "0.85em" }}>
          <code>Mã tiêu chí: {criterion.tieu_chi_id}</code> | <code>Mô hình: {criterion.model_version}</code> | <code>Prompt: {criterion.prompt_version}</code>
        </p>
      </details>

      {risks.length > 0 && (
        <div className="links">
          Rủi ro:{" "}
          {risks.map((r) => (
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
    </article>
  );
}
