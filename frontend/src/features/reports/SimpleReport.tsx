import { useContext } from "react";

import type {
  CriterionResult,
  FinalReport,
  ReportContent,
  RequirementResult,
  RiskResult,
} from "../../shared/api/client";
import { StatusBadge, stripEngineMarks } from "../../shared/components/ui";
import { fieldLabel } from "../../shared/fieldLabels";
import { label } from "../../shared/labels";
import { profileValue, roleLabel } from "../../shared/profileValues";
import { displayText } from "../../shared/text";
import { setViewMode } from "../../shared/viewMode";
import { useOpenEvidence } from "../assessments/evidence/EvidenceViewer";
import { requirementDisplayStatus, useReportPresentation } from "./assessmentStatus";
import { useInsufficientCauses } from "./causes";
import { aiUsage, type Cause } from "./explain";
import { LegalBasis, LegalBasisContext } from "./legalBasis";
import { directAction, readRecommendation } from "./recommendation";
import {
  criterionText,
  requirementIdOf,
  requirementText,
  riskTitle,
  useReportIndex,
  useRequirementGroup,
  useRequirementName,
} from "./reportIndex";
import { topicTitle } from "./topics";

type Tone = "good" | "warn" | "bad" | "unknown";

/** One requirement the reader should look at, with the checks that failed in it. */
type Issue = { key: string; requirement?: RequirementResult; criteria: CriterionResult[] };

const VIETNAMESE = /[ăâđêôơưàáạảãèéẹẻẽìíịỉĩòóọỏõùúụủũỳýỵỷỹ]/i;
// Words the engine writes for engineers; a sentence carrying them is not shown to general users.
const ENGINE_WORDS = /\b(?:finding|gate|VIOLATED|MISSING|UNKNOWN|HIGH|MEDIUM|LOW|quy_tac\w*|TC_[A-Z0-9_]+)\b/;

/** Stored machine text as a reader sentence, or null when it is an engine trace. */
function plain(text: string | null | undefined): string | null {
  const clean = text ? stripEngineMarks(text) : "";
  return clean && VIETNAMESE.test(clean) && !ENGINE_WORDS.test(clean) ? clean : null;
}

/** The first sentence of a risk description says what can go wrong; the rest is engine notes. */
function consequence(risk: RiskResult): string | null {
  const text = (risk.risk_snapshot as { mo_ta?: string } | undefined)?.mo_ta ?? "";
  const first = text.split(/(?<=\.)\s+/)[0] ?? "";
  return plain(first);
}

const FAILED = new Set(["VIOLATED", "MISSING"]);
// Who can resolve a requirement the system could not conclude: the contract's author (the
// contract lacks a fact or a clause), a legal reviewer, or nobody yet (a system limit).
const FROM_CONTRACT = new Set<Cause>(["PARTY", "MISSING_FACT", "DATE", "NO_EVIDENCE"]);
const FROM_REVIEWER = new Set<Cause>(["NEEDS_REVIEWER", "AI_PENDING"]);
// Actions that ask for a check; the others change the contract.
const CHECK_ACTIONS = new Set(["VERIFY", "VERIFY_REFERENCE", "REQUEST_VERIFICATION", "REQUEST_EVIDENCE"]);
// Missing contract facts as the question the contract leaves open (field names read as labels).
const OPEN_QUESTIONS: Record<string, string> = {
  la_nha_o_xa_hoi: "căn hộ có phải nhà ở xã hội không",
  la_nha_xay_moi: "căn hộ có phải nhà xây mới không",
  la_giao_dich_dien_tu: "hợp đồng có được giao kết bằng phương thức điện tử không",
  la_hop_dong_theo_mau: "có dùng hợp đồng theo mẫu không",
  co_thoa_thuan_trong_tai: "có thỏa thuận trọng tài không",
  co_thoa_thuan_dat_coc: "có thỏa thuận đặt cọc không",
  ben_ban_co_von_nuoc_ngoai: "bên bán có vốn nước ngoài không",
  tinh_trang_tai_san: "nhà có sẵn hay hình thành trong tương lai",
};
const CITATION_ORDER = ["INVALID", "STALE", "UNKNOWN"];
const CITATION_WORDS: Record<string, string> = {
  VALID: "hợp lệ",
  STALE: "đã hết hiệu lực hoặc bị thay thế",
  INVALID: "không hợp lệ",
  UNKNOWN: "chưa xác minh được",
};

/**
 * The report for general users: one conclusion, the points to look at (what the rule asks, what
 * the contract says, what to do) and nothing else. It reads the same stored statuses as the
 * advanced view and never recomputes one; it only shows fewer of them.
 */
export function SimpleReport({ report }: { report: FinalReport }) {
  const content = report.report_json;
  const index = useReportIndex();
  const results = content.compliance.requirement_results;
  const shown = results.map(requirementDisplayStatus);
  const count = (code: string) => shown.filter((s) => s === code).length;
  const ok = count("COMPLIANT");
  const insufficient = count("INSUFFICIENT");
  const outside = count("OUTSIDE_REVIEW_SCOPE");
  const causes = useInsufficientCauses(content);
  const nameOf = useRequirementName();
  const groupOf = useRequirementGroup();
  const topicOf = (key: string) => {
    const group = groupOf(requirementIdOf(index, key));
    return group ? topicTitle(group) : null;
  };

  // Same definition of "needs attention" as the advanced overview: requirements that are not
  // met, plus the compliance and citation risks found.
  const issues = new Map<string, Issue>();
  const flagged = results
    .filter((r) => r.status === "NON_COMPLIANT" || r.status === "PARTIAL")
    .sort((a, b) => (a.status === b.status ? 0 : a.status === "NON_COMPLIANT" ? -1 : 1));
  for (const r of flagged)
    issues.set(r.yeu_cau_ca_id, {
      key: r.yeu_cau_ca_id,
      requirement: r,
      criteria: (index.criteriaByRequirement.get(r.yeu_cau_ca_id) ?? []).filter(
        (c) => !c.excluded && FAILED.has(c.finding),
      ),
    });
  // The two branches stay apart (BRD 8.8, AC-11): compliance issues come from the applicable
  // law, citation issues from the legal documents the contract itself names.
  const citationRisks = content.risks.citation;
  const looseRisks: RiskResult[] = [];
  for (const risk of content.risks.compliance) {
    const criterion = risk.source.ket_qua_tieu_chi_id
      ? index.criterionById.get(risk.source.ket_qua_tieu_chi_id)
      : undefined;
    if (!criterion) {
      looseRisks.push(risk);
      continue;
    }
    const issue = issues.get(criterion.yeu_cau_ca_id) ?? {
      key: criterion.yeu_cau_ca_id,
      requirement: index.requirementById.get(criterion.yeu_cau_ca_id),
      criteria: [],
    };
    if (!issue.criteria.includes(criterion)) issue.criteria.push(criterion);
    issues.set(issue.key, issue);
  }
  const issueList = [...issues.values()];
  const complianceCount = issueList.length + looseRisks.length;
  const attention = complianceCount + citationRisks.length;
  const findings = content.citation_validation.findings;
  const citationCount = (code: string) => findings.filter((f) => f.status === code).length;
  const citationProblems = findings
    .filter((f) => f.status !== "VALID")
    .sort((a, b) => CITATION_ORDER.indexOf(a.status) - CITATION_ORDER.indexOf(b.status));
  const anyViolation = flagged.some((r) => r.status === "NON_COMPLIANT");
  const topics = [...new Set(issueList.map((issue) => topicOf(issue.key)).filter(Boolean))].slice(0, 3);

  // Why the rest has no conclusion, by who can do something about it.
  const sum = (keep: (cause: Cause) => boolean) =>
    causes.filter(([cause]) => keep(cause)).reduce((n, [, entry]) => n + entry.count, 0);
  const fromContract = sum((c) => FROM_CONTRACT.has(c));
  const fromReviewer = sum((c) => FROM_REVIEWER.has(c));
  const fromSystem = insufficient - fromContract - fromReviewer;
  const missing = new Map<string, number>();
  for (const [cause, entry] of causes)
    if (FROM_CONTRACT.has(cause))
      for (const [field, n] of entry.fields) missing.set(field, (missing.get(field) ?? 0) + n);
  const missingFields = [...missing]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([field]) => OPEN_QUESTIONS[field] ?? fieldLabel(field).toLowerCase());

  const head: { tone: Tone; title: string; text: string } =
    results.length === 0
      ? {
          tone: "unknown",
          title: "Chưa có kết quả kiểm tra",
          text: "Lần phân tích này chưa tạo được kết quả. Hãy thử phân tích lại hợp đồng.",
        }
      : attention > 0
        ? {
            tone: anyViolation ? "bad" : "warn",
            title: `Hợp đồng có ${attention} điểm cần xem lại`,
            text: `${topics.length ? `Liên quan đến: ${topics.join("; ")}. ` : ""}Từng điểm được nêu bên dưới, kèm đoạn hợp đồng liên quan và việc nên làm.`,
          }
        : insufficient > 0
          ? {
              tone: "unknown",
              title: "Chưa phát hiện dấu hiệu trái quy định",
              text: `Tuy nhiên còn ${insufficient} nội dung hệ thống chưa đủ thông tin để kết luận, nên chưa thể khẳng định hợp đồng đáp ứng đầy đủ.`,
            }
          : ok > 0
            ? {
                tone: "good",
                title: "Chưa phát hiện vấn đề nào",
                text: `Hợp đồng đáp ứng cả ${ok} nội dung đã kiểm tra.`,
              }
            : {
                tone: "unknown",
                title: "Không có nội dung nào cần kết luận",
                text: "Các quy định được xét đều không áp dụng cho hợp đồng này trong phạm vi đã chọn.",
              };

  const titleOf = (issue: Issue) =>
    nameOf(requirementIdOf(index, issue.key)) ??
    (issue.requirement ? requirementText(issue.requirement) : null) ??
    (issue.criteria[0] ? criterionText(issue.criteria[0]) : "Quy định chưa có tên");
  const passed = results.filter((r) => requirementDisplayStatus(r) === "COMPLIANT");
  const { total, called } = aiUsage(content.compliance.criterion_results);

  const notes = [
    report.report_status === "PUBLISHED"
      ? "Báo cáo này đã được chuyên viên duyệt và phát hành."
      : "Đây là kết quả do máy phân tích, chưa được chuyên viên pháp lý duyệt. Chỉ nên dùng để tham khảo.",
    "Hệ thống là công cụ hỗ trợ rà soát, không thay thế ý kiến của luật sư hoặc quyết định của cơ quan có thẩm quyền.",
    ...(total > 0 && called === 0
      ? ["Lần phân tích này chưa dùng AI để đọc nội dung điều khoản, nên phần lớn nội dung chưa kết luận được."]
      : []),
    ...(outside > 0
      ? ["Hệ thống chỉ kiểm tra nội dung các điều khoản. Việc thực hiện hợp đồng (ký kết, thu tiền, bàn giao) chưa được kiểm tra."]
      : []),
  ];

  return (
    <div className="simple-report">
      <ContractFacts content={content} />

      <section className={`verdict tone-${head.tone}`} aria-label="Kết luận">
        <p className="verdict-kicker">Kết luận</p>
        <h2>{head.title}</h2>
        <p>{head.text}</p>
      </section>

      {results.length > 0 && (
        <ul className="simple-counts" aria-label="Tóm tắt kết quả">
          <li className={attention ? "tone-bad" : undefined}>
            <strong>{attention}</strong>
            <span>cần xem lại</span>
          </li>
          <li>
            <strong>{ok}</strong>
            <span>đạt yêu cầu</span>
          </li>
          <li>
            <strong>{insufficient}</strong>
            <span>chưa kết luận được</span>
          </li>
        </ul>
      )}

      {complianceCount > 0 && (
        <section aria-label="Nội dung chưa đáp ứng quy định pháp luật">
          <h3 className="simple-head">Nội dung chưa đáp ứng quy định pháp luật</h3>
          <ol className="issue-list">
            {issueList.map((issue, i) => (
              <li key={issue.key} className="issue">
                <IssueHead
                  number={i + 1}
                  topic={topicOf(issue.key)}
                  title={titleOf(issue)}
                  bad={
                    issue.requirement?.status === "NON_COMPLIANT" ||
                    issue.criteria.some((c) => c.finding === "VIOLATED")
                  }
                />
                {issue.criteria.length === 0 && (
                  <p className="muted">
                    Hệ thống ghi nhận quy định này chưa được đáp ứng đầy đủ. Xem chi tiết ở chế độ
                    Nâng cao.
                  </p>
                )}
                {issue.criteria.map((c) => (
                  <CriterionIssue key={c.ket_qua_id} criterion={c} title={titleOf(issue)} />
                ))}
              </li>
            ))}
            {looseRisks.map((risk, i) => (
              <li key={risk.ket_qua_rui_ro_id} className="issue">
                <IssueHead number={issueList.length + i + 1} topic={null} title={riskTitle(risk)} bad={false} />
                {plain(risk.giai_thich) && <p>{plain(risk.giai_thich)}</p>}
                <WhatToDo risks={[risk]} />
              </li>
            ))}
          </ol>
        </section>
      )}

      {findings.length > 0 && (
        <section aria-label="Văn bản pháp luật hợp đồng viện dẫn">
          <h3 className="simple-head">Văn bản pháp luật hợp đồng viện dẫn</h3>
          <p className="simple-line">
            Hợp đồng viện dẫn {findings.length} văn bản pháp luật:{" "}
            {CITATION_ORDER.concat("VALID")
              .filter((code) => citationCount(code) > 0)
              .map((code) => `${citationCount(code)} ${CITATION_WORDS[code]}`)
              .join(", ")}
            . Phần này chỉ kiểm tra văn bản hợp đồng tự nêu có đúng và còn hiệu lực hay không,
            tách riêng với việc hợp đồng có đáp ứng quy định ở trên.
          </p>
          {citationProblems.length > 0 && (
            <ul className="issue-list">
              {citationProblems.map((f) => {
                const reason = label("reasonCode", f.reason_code);
                return (
                  <li key={f.finding_id} className="issue">
                    <header className="issue-head">
                      <h4>{index.citationById.get(f.vien_dan_id)?.raw_text ?? "Viện dẫn trong hợp đồng"}</h4>
                      <StatusBadge kind="citation" code={f.status} />
                    </header>
                    <p className="issue-reason">
                      {reason.text !== f.reason_code ? `${reason.text}.` : plain(f.ly_do)}
                      {f.status === "UNKNOWN" && " Cần chuyên viên xác minh; đây chưa phải là kết luận viện dẫn sai."}
                    </p>
                    <WhatToDo
                      risks={(index.risksByFinding.get(f.finding_id) ?? []).filter(
                        (r) => r.risk_type === "CITATION",
                      )}
                    />
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}

      {passed.length > 0 && (
        <details className="simple-more">
          <summary>
            {passed.length} nội dung đạt yêu cầu
          </summary>
          <ul>
            {passed.map((r) => (
              <li key={r.tuan_thu_id}>
                {nameOf(requirementIdOf(index, r.yeu_cau_ca_id)) ?? requirementText(r)}
              </li>
            ))}
          </ul>
        </details>
      )}

      {insufficient > 0 && (
        <section className="panel" aria-label="Nội dung chưa kết luận được">
          <h3>{insufficient} nội dung chưa kết luận được</h3>
          <p className="simple-line">
            Đây không phải là vi phạm. Hệ thống chỉ kết luận khi có đủ thông tin và bằng chứng.
          </p>
          <ul className="pending-list">
            {fromContract > 0 && (
              <li>
                <strong>{fromContract} nội dung cần thêm thông tin từ hợp đồng.</strong>{" "}
                {missingFields.length > 0
                  ? `Hợp đồng chưa ghi rõ: ${missingFields.join("; ")}. Làm rõ các thông tin này trong hợp đồng hoặc phụ lục rồi kiểm tra lại.`
                  : "Hệ thống chưa tìm thấy điều khoản hoặc thông tin liên quan trong hợp đồng."}
              </li>
            )}
            {fromReviewer > 0 && (
              <li>
                <strong>{fromReviewer} nội dung cần chuyên viên pháp lý xác minh</strong> trước khi
                kết luận.
              </li>
            )}
            {fromSystem > 0 && (
              <li>
                <strong>{fromSystem} nội dung hệ thống hiện chưa tự đánh giá được.</strong> Đây là
                giới hạn của hệ thống, không phải do hợp đồng.
              </li>
            )}
          </ul>
        </section>
      )}

      <section className="panel" aria-label="Bước tiếp theo">
        <h3>Bước tiếp theo</h3>
        <ol className="next-steps">
          {attention > 0 && (
            <li>
              Sửa hoặc bổ sung các điểm nêu trên trong hợp đồng (hợp đồng đã ký thì sửa bằng phụ
              lục), rồi tải bản mới lên để kiểm tra lại.
            </li>
          )}
          {report.report_status === "PUBLISHED" ? (
            <li>Báo cáo đã được chuyên viên duyệt; tải bản PDF ở đầu trang để lưu hoặc gửi đi.</li>
          ) : (
            <li>
              Trước khi dùng kết quả cho việc quan trọng, nhờ chuyên viên pháp lý rà soát. Chuyên
              viên xem đầy đủ từng quy định và căn cứ ở{" "}
              <button type="button" className="link" onClick={() => setViewMode("advanced")}>
                chế độ Nâng cao
              </button>
              .
            </li>
          )}
        </ol>
      </section>

      <section className="panel notes" aria-label="Lưu ý">
        <h3>Lưu ý</h3>
        <ul>
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </section>

    </div>
  );
}

/** What the system read, so the reader can see at once it is their contract and read right. */
function ContractFacts({ content }: { content: ReportContent }) {
  const profile = content.contract_profile.profile as Record<string, unknown>;
  const value = (field: string) => profileValue(field, profile[field], profile);
  const rows: [string, string | null][] = [
    ...(content.contract_profile.subjects ?? [])
      .filter((s) => s.ten_chu_the)
      .map((s): [string, string | null] => [roleLabel(s.vai_tro), s.ten_chu_the ?? null]),
    ["Ngày ký", value("ngay_giao_ket")],
    ["Giá trị hợp đồng", value("gia_tri_hop_dong")],
  ];
  const handover = value("ngay_ban_giao_du_kien");
  if (handover) rows.push(["Bàn giao dự kiến", handover]);
  return (
    <section className="contract-facts" aria-label="Thông tin đọc được từ hợp đồng">
      <p className="verdict-kicker">
        Hệ thống đọc được từ hợp đồng
        {value("loai_hop_dong_id") && ` · ${value("loai_hop_dong_id")}`}
      </p>
      <dl>
        {rows.map(([name, text]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>{text ?? <span className="null">chưa đọc được</span>}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function IssueHead({
  number,
  topic,
  title,
  bad,
}: {
  number: number;
  topic: string | null;
  title: string;
  bad: boolean;
}) {
  return (
    <header className="issue-head">
      <span className="issue-num">{number}</span>
      <h4>
        {topic && <span className="issue-topic">{topic}</span>}
        {title}
      </h4>
      {/* A machine finding is a sign to check, not a legal ruling (BRD 4.2). */}
      <span className={`badge tone-${bad ? "bad" : "warn"}`}>
        {bad ? "Có dấu hiệu trái quy định" : "Thiếu nội dung"}
      </span>
    </header>
  );
}

/** One failed check: what the rule asks, what the contract says, why it matters, what to do. */
function CriterionIssue({ criterion, title }: { criterion: CriterionResult; title: string }) {
  const index = useReportIndex();
  const openEvidence = useOpenEvidence();
  const known = useContext(LegalBasisContext);
  const view = useReportPresentation()?.criteria[criterion.ket_qua_id];
  const risks = index.risksByCriterion.get(criterion.ket_qua_id) ?? [];
  const found = risks.filter((r) => r.risk_type !== "VERIFICATION");
  // A long contract is read in batches and each batch leaves its own note ("…; Batch này …;
  // D11 có …"). The first note states the finding; chunk labels (D16) mean nothing to a reader.
  const explanation = plain(
    stripEngineMarks(view?.explanation ?? criterion.giai_thich ?? "")
      .split(/;\s+/)[0]
      ?.replace(/\s+(?:\S+\s+)?D\d+(?!\w)/g, "") // "… tại D16": the label and its preposition
      .replace(/[.\s]*$/, "."),
  );
  const why = found.map(consequence).find(Boolean);
  const severity = found.map((r) => r.severity).find((code) => code && code !== "REVIEW_REQUIRED");
  const priority = severity ? label("severity", severity).text : null;
  // The law's article and document are enough here; the catalogue's own entry stays in Advanced.
  const ofKind = (kind: string) =>
    (criterion.legal_basis_ids ?? []).filter((id) => known.get(id)?.kind === kind);
  const basis = ofKind("DOCUMENT").length ? ofKind("DOCUMENT") : ofKind("ARTICLE");
  return (
    <div className="issue-body">
      <dl className="issue-facts">
        {/* Often the requirement is named by its only check; do not say it twice. */}
        {criterionText(criterion).trim() !== title.trim() && (
          <div>
            <dt>Quy định yêu cầu</dt>
            <dd>{criterionText(criterion)}</dd>
          </div>
        )}
        <div>
          <dt>Trong hợp đồng</dt>
          <dd>
            {explanation ??
              (criterion.finding === "MISSING"
                ? "Hợp đồng thiếu nội dung mà quy định yêu cầu."
                : `${label("criterion", criterion.finding).text}.`)}
            {(criterion.evidence ?? []).slice(0, 2).map((e, i) => (
              <figure key={`${e.doan_id}-${i}`} className="issue-quote">
                <blockquote>“{displayText(e.trich_dan).replace(/\s*\n\s*/g, " ")}”</blockquote>
                {openEvidence && (
                  <button
                    type="button"
                    className="link small"
                    onClick={() =>
                      openEvidence({
                        doanId: e.doan_id,
                        start: e.ky_tu_bat_dau,
                        end: e.ky_tu_ket_thuc,
                        quote: e.trich_dan,
                      })
                    }
                  >
                    Xem trong hợp đồng
                  </button>
                )}
              </figure>
            ))}
          </dd>
        </div>
        {why && (
          <div>
            <dt>Rủi ro có thể gặp</dt>
            <dd>
              {why}
              {priority && <span className="muted"> Ưu tiên xử lý: {priority.toLowerCase()}.</span>}
            </dd>
          </div>
        )}
        {basis.length > 0 && (
          <div>
            <dt>Căn cứ</dt>
            <dd>
              <LegalBasis ids={basis} />
            </dd>
          </div>
        )}
      </dl>
      <WhatToDo risks={found.length ? found : risks} />
    </div>
  );
}

function WhatToDo({ risks }: { risks: RiskResult[] }) {
  const index = useReportIndex();
  const presentation = useReportPresentation();
  const actions = [
    ...new Set(
      risks
        .flatMap((r) => index.recommendationsByRisk.get(r.ket_qua_rui_ro_id) ?? [])
        .map((k) => {
          const text = presentation?.recommendations[k.khuyen_nghi_ca_id]?.text ?? k.noi_dung;
          return CHECK_ACTIONS.has(k.loai_hanh_dong)
            ? readRecommendation(text).action
            : directAction(text);
        }),
    ),
  ];
  if (!actions.length) return null;
  return (
    <div className="recommendation">
      <span className="recommendation-label">Nên làm gì</span>
      {actions.map((action) => (
        <p key={action}>{action}</p>
      ))}
    </div>
  );
}
