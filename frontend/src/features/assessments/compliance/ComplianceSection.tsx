import type {
  CriterionResult,
  ReportContent,
  RequirementResult,
} from "../../../shared/api/client";
import {
  Empty,
  Ids,
  Notice,
  Quote,
  Section,
  StatusBadge,
} from "../../../shared/components/ui";
import { focusDomId, useReportNav } from "../../reports/nav";
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
  coverage_complete: "Đủ độ phủ tài liệu",
  absence_verified: "Đã xác minh vắng nội dung",
  exceptions_resolved: "Đã xét ngoại lệ",
  evidence_conflict: "Bằng chứng mâu thuẫn",
};

export function ComplianceSection({ content }: { content: ReportContent }) {
  const index = useReportIndex();
  const results = content.compliance.requirement_results;
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
  const index = useReportIndex();
  const { focus } = useReportNav();
  const criteria = index.criteriaByRequirement.get(requirement.yeu_cau_ca_id) ?? [];
  const applicable = index.applicableById.get(requirement.yeu_cau_ca_id);
  const containsFocus =
    focus === requirement.yeu_cau_ca_id || criteria.some((c) => c.ket_qua_id === focus);
  const version = (requirement.requirement_snapshot_json as { version?: Record<string, unknown> })
    .version;

  return (
    <details
      className="card"
      id={focusDomId(requirement.yeu_cau_ca_id)}
      open={containsFocus || undefined}
    >
      <summary className="card-summary">
        <StatusBadge kind="requirement" code={requirement.status} />
        <span className="card-title">{requirementText(requirement)}</span>
        <span className="muted small">
          đã đánh giá {requirement.so_tieu_chi_da_danh_gia}/{requirement.so_tieu_chi_ap_dung} tiêu
          chí · {requirement.so_unknown} chưa xác định
          {!requirement.coverage_complete && " · chưa đủ độ phủ"}
        </span>
      </summary>
      <div className="card-body">
        <p>{requirement.giai_thich}</p>
        <dl className="fields compact">
          <div>
            <dt>Yêu cầu</dt>
            <dd>
              <code>{requirement.yeu_cau_ca_id}</code>
            </dd>
          </div>
          <div>
            <dt>Phiên bản</dt>
            <dd>
              <code>{applicable?.requirement_version_id ?? "chưa rõ"}</code>{" "}
              <StatusBadge kind="version" code={applicable?.version_status} />{" "}
              <StatusBadge kind="applicability" code={applicable?.applicability_status} />
            </dd>
          </div>
          <div>
            <dt>Căn cứ</dt>
            <dd>
              <Ids
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
            <dt>Rule</dt>
            <dd>
              <code>{requirement.rule_version}</code>
            </dd>
          </div>
        </dl>
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
  const risks = index.risksByCriterion.get(criterion.ket_qua_id) ?? [];
  const snapshot = (criterion.tieu_chi_snapshot_json as { criterion?: Record<string, unknown> })
    .criterion;
  const basisText = typeof snapshot?.can_cu_cu_the === "string" ? snapshot.can_cu_cu_the : null;
  const basisUrl = typeof snapshot?.url_can_cu === "string" ? snapshot.url_can_cu : null;
  const gates = Object.entries(criterion.gates);

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
      <p>{criterion.giai_thich}</p>
      {criterion.uncertainty_reason && (
        <p className="uncertain">Chưa chắc chắn: {criterion.uncertainty_reason}</p>
      )}

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

      <h4 className="minihead">Bằng chứng trong hợp đồng</h4>
      {criterion.evidence?.length ? (
        criterion.evidence.map((e, i) => (
          <Quote
            key={`${e.doan_id}-${i}`}
            text={e.trich_dan}
            chunkId={e.doan_id}
            start={e.ky_tu_bat_dau}
            end={e.ky_tu_ket_thuc}
          />
        ))
      ) : (
        <Empty>Chưa có bằng chứng được chọn (truy xuất rỗng, không đồng nghĩa với MISSING).</Empty>
      )}
      {criterion.external_evidence?.map((e) => (
        <p key={e.bang_chung_id} className="small">
          Chứng từ ngoài <code>{e.bang_chung_id}</code> {e.verified ? "(đã xác minh)" : "(chưa xác minh)"}
        </p>
      ))}

      <dl className="fields compact">
        <div>
          <dt>Căn cứ hệ thống</dt>
          <dd>
            <Ids ids={criterion.legal_basis_ids} />
            {basisText && <span className="small"> {basisText}</span>}{" "}
            {basisUrl && (
              <a href={basisUrl} target="_blank" rel="noreferrer">
                nguồn
              </a>
            )}
          </dd>
        </div>
        <div>
          <dt>Model / prompt</dt>
          <dd>
            <code>{criterion.model_version}</code> / <code>{criterion.prompt_version}</code>
          </dd>
        </div>
        <div>
          <dt>Review</dt>
          <dd>
            <StatusBadge kind="review" code={criterion.review_status} />
          </dd>
        </div>
      </dl>

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
