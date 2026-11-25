import { useSearchParams } from "react-router-dom";

import type { FinalReport, ReportContent } from "../../shared/api/client";
import { fieldLabel } from "../../shared/fieldLabels";
import { label } from "../../shared/labels";
import { requirementDisplayStatus } from "./assessmentStatus";
import { NEXT_STEP, useInsufficientCauses } from "./causes";
import { aiUsage, type Cause, CAUSES, viDate } from "./explain";
import { useReportNav } from "./nav";
import { useReportIndex } from "./reportIndex";
import {
  RequirementCard,
  useRequirementReason,
} from "../assessments/compliance/ComplianceSection";
import { RiskCard } from "../assessments/risks/RisksSection";

type Tone = "good" | "warn" | "bad" | "unknown";

/** One headline from the stored statuses; nothing is scored or recomputed. */
function verdict(content: ReportContent): { tone: Tone; title: string; text: string } {
  const results = content.compliance.requirement_results;
  const shown = results.map(requirementDisplayStatus);
  const n = (code: string) => shown.filter((s) => s === code).length;
  const [bad, partial, ok, unknown] = [n("NON_COMPLIANT"), n("PARTIAL"), n("COMPLIANT"), n("INSUFFICIENT")];
  // Rows outside the chosen review scope or not triggered are neither met nor missing.
  const assessed = results.length - n("OUTSIDE_REVIEW_SCOPE") - n("NOT_TRIGGERED");
  if (results.length === 0)
    return {
      tone: "unknown",
      title: "Chưa có kết quả đánh giá",
      text: "Lần chạy này chưa tạo được kết quả cho quy định nào.",
    };
  if (bad > 0)
    return {
      tone: "bad",
      title: `Phát hiện ${bad} quy định hợp đồng không tuân thủ`,
      text: "Xem mục “Cần chú ý” để biết điều khoản nào và căn cứ pháp lý.",
    };
  if (partial > 0)
    return {
      tone: "warn",
      title: `${partial} quy định chỉ được tuân thủ một phần`,
      text: "Xem mục “Cần chú ý” để biết phần nào còn thiếu.",
    };
  if (assessed === 0)
    return {
      tone: "unknown",
      title: "Không có quy định nào cần kết luận trong phạm vi đã chọn",
      text: "Các quy định được xét đều nằm ngoài phạm vi rà soát hoặc không phát sinh nghĩa vụ.",
    };
  if (ok === assessed)
    return {
      tone: "good",
      title: `Hợp đồng đáp ứng cả ${ok} quy định đã kiểm tra`,
      text: `Kết quả vẫn cần chuyên viên duyệt trước khi dùng chính thức.`,
    };
  if (unknown === assessed)
    return {
      tone: "unknown",
      title: "Chưa đủ căn cứ để kết luận",
      text: `Hệ thống chưa phát hiện vi phạm nào, nhưng cả ${unknown} quy định đã kiểm tra đều còn thiếu thông tin để kết luận. Lý do và việc cần làm ở bên dưới.`,
    };
  return {
    tone: "unknown",
    title: `${ok} quy định tuân thủ, ${unknown} quy định chưa đủ căn cứ`,
    text: `Đã kiểm tra ${assessed} quy định, chưa phát hiện vi phạm. Các quy định chưa đủ căn cứ cần bổ sung thông tin.`,
  };
}

export function OverviewSection({ report }: { report: FinalReport }) {
  const content = report.report_json;
  const { go } = useReportNav();
  const [, setParams] = useSearchParams();
  const results = content.compliance.requirement_results;
  const scope = content.applicable_legal_scope;
  const notApplicable = scope.filter((a) => a.applicability_status === "NOT_APPLICABLE").length;
  const attention = results
    .filter((r) => r.status === "NON_COMPLIANT" || r.status === "PARTIAL")
    .sort((a, b) => (a.status === b.status ? 0 : a.status === "NON_COMPLIANT" ? -1 : 1));
  const foundRisks = [...content.risks.compliance, ...content.risks.citation];
  const attentionCount = attention.length + foundRisks.length;
  const reasonOf = useRequirementReason();
  const index = useReportIndex();
  const toAttention = () =>
    document.getElementById("attention-block")?.scrollIntoView({ block: "start", behavior: "smooth" });
  const shownStatus = results.map(requirementDisplayStatus);
  const insufficient = shownStatus.filter((s) => s === "INSUFFICIENT").length;
  const outside = shownStatus.filter((s) => s === "OUTSIDE_REVIEW_SCOPE").length;
  const notTriggered = shownStatus.filter((s) => s === "NOT_TRIGGERED").length;
  const assessed = results.length - outside - notTriggered;
  const causes = useInsufficientCauses(content);
  const head = verdict(content);

  const showCause = (cause: Cause) =>
    setParams((params) => {
      const next = new URLSearchParams({ tab: "topics", cause });
      const view = params.get("view");
      if (view) next.set("view", view);
      return next;
    });

  const steps = [
    ...(attentionCount ? ["Xem phần “Cần chú ý” bên dưới và xử lý từng điểm."] : []),
    ...causes.map(([cause]) => NEXT_STEP[cause]).filter((s): s is string => !!s),
    report.report_status === "PUBLISHED"
      ? "Báo cáo đã phát hành; mọi chỉnh sửa sau này tạo phiên bản mới."
      : "Khi đã đủ thông tin, chuyên viên duyệt và phát hành báo cáo ở mục “Rà soát và phát hành”.",
  ];

  return (
    <div className="overview">
      <section className={`verdict tone-${head.tone}`} aria-label="Kết luận">
        <p className="verdict-kicker">Kết luận</p>
        <h2>{head.title}</h2>
        <p>{head.text}</p>
      </section>

      <div className="stats">
        <button type="button" className="stat" onClick={() => go("topics")}>
          <strong>{assessed}</strong>
          <span>quy định đã kiểm tra</span>
          <small>
            {[
              `trên ${scope.length} quy định đã đối chiếu`,
              `${notApplicable} không áp dụng`,
              outside ? `${outside} ngoài phạm vi rà soát dự thảo` : null,
              notTriggered ? `${notTriggered} không phát sinh điều kiện` : null,
            ]
              .filter(Boolean)
              .join(", ")}
          </small>
        </button>
        <button
          type="button"
          className={`stat${attentionCount ? " tone-bad" : ""}`}
          onClick={toAttention}
        >
          <strong>{attentionCount}</strong>
          <span>cần chú ý</span>
          <small>quy định không đạt hoặc rủi ro phát hiện được</small>
        </button>
        <button type="button" className="stat" onClick={() => go("topics")}>
          <strong>{insufficient}</strong>
          <span>chưa đủ căn cứ</span>
          <small>thiếu thông tin để kết luận, không phải vi phạm</small>
        </button>
      </div>

      <section className="panel" id="attention-block" aria-label="Cần chú ý">
        <h3>Cần chú ý ({attentionCount})</h3>
        {attentionCount === 0 ? (
          <p className="muted">
            Chưa phát hiện quy định nào không đạt hoặc rủi ro nào.
            {insufficient > 0 &&
              ` Vì còn ${insufficient} quy định chưa đủ căn cứ, chưa thể khẳng định hợp đồng đáp ứng đầy đủ.`}
          </p>
        ) : (
          <div className="stack">
            {attention.map((r) => (
              <RequirementCard key={r.tuan_thu_id} requirement={r} reason={reasonOf(r).text} />
            ))}
            {foundRisks.map((r) => (
              <RiskCard
                key={r.ket_qua_rui_ro_id}
                risk={r}
                recommendations={index.recommendationsByRisk.get(r.ket_qua_rui_ro_id) ?? []}
              />
            ))}
          </div>
        )}
      </section>

      <ResultNotes report={report} />

      {causes.length > 0 && (
        <section className="panel">
          <h3>Vì sao {insufficient} quy định chưa kết luận được</h3>
          <ul className="cause-list">
            {causes.map(([cause, { count, fields }]) => {
              const topFields = [...fields]
                .sort((a, b) => b[1] - a[1])
                .slice(0, 4)
                .map(([f]) => fieldLabel(f));
              return (
                <li key={cause}>
                  <span className="cause-count">{count}</span>
                  <span className="cause-title">
                    {CAUSES[cause].title}{" "}
                    <button type="button" className="link small" onClick={() => showCause(cause)}>
                      Xem các quy định này →
                    </button>
                  </span>
                  <span className="cause-hint">
                    {CAUSES[cause].hint}
                    {topFields.length > 0 && ` Thông tin còn thiếu: ${topFields.join(", ")}.`}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section className="panel">
        <h3>Việc nên làm tiếp</h3>
        <ol className="next-steps">
          {[...new Set(steps)].map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>
    </div>
  );
}

/** Everything a reader must know before trusting the numbers, in one box instead of banners. */
function ResultNotes({ report }: { report: FinalReport }) {
  const content = report.report_json;
  const { total, called } = aiUsage(content.compliance.criterion_results);
  const assessed = content.case.assessment_context;
  const notes: string[] = [];
  notes.push(
    report.report_status === "PUBLISHED"
      ? "Báo cáo đã được chuyên viên duyệt và phát hành."
      : `Đây là kết quả máy, chưa được chuyên viên duyệt (${label("reportStatus", report.report_status).text.toLowerCase()}). Không dùng như ý kiến pháp lý chính thức.`,
  );
  if (total > 0 && called === 0)
    notes.push(
      "Lần chạy này không dùng AI, nên hệ thống chưa đọc hiểu nội dung từng điều khoản: mọi điểm kiểm tra là “chưa xác định”.",
    );
  else if (called < total)
    notes.push(`AI đã đọc ${called}/${total} điểm kiểm tra (mỗi lần chạy có giới hạn số lượt gọi AI).`);
  if (content.audit.module_source === "MODULES_DI_REFERENCE")
    notes.push(
      "Tệp gốc không có trên máy chủ nên nội dung hợp đồng lấy từ bộ dữ liệu mẫu; các bước đánh giá vẫn chạy thật.",
    );
  if (content.audit.module_source === "REFERENCE_REPLAY")
    notes.push("Bản chạy thử tích hợp (phát lại đáp án mẫu), không phải kết quả đánh giá hợp đồng.");
  if (content.audit.evidence_mode === "SYNTHETIC")
    notes.push(
      "Ca này dùng chứng từ và dữ kiện giả lập (chế độ đồ án); kết quả được tính theo kịch bản giả lập đó.",
    );
  const shown = content.compliance.requirement_results.map(requirementDisplayStatus);
  const outside = shown.filter((s) => s === "OUTSIDE_REVIEW_SCOPE").length;
  const notTriggered = shown.filter((s) => s === "NOT_TRIGGERED").length;
  if (assessed.review_mode === "DRAFT_REVIEW")
    notes.push(
      `Đây là rà soát dự thảo trước khi ký: hệ thống chỉ kiểm tra nội dung các điều khoản.${
        outside
          ? ` ${outside} quy định cần giấy tờ về việc thực hiện hợp đồng (đã ký, thu tiền, bàn giao…) nên chưa được đánh giá và không được coi là đã đáp ứng.`
          : ""
      }`,
    );
  else if (outside)
    notes.push(`${outside} quy định nằm ngoài phạm vi đánh giá đã chọn và không được coi là đã đáp ứng.`);
  if (notTriggered)
    notes.push(
      `${notTriggered} quy định không phát sinh nghĩa vụ cho hợp đồng này sau khi xét điều kiện riêng.`,
    );
  const signed = content.contract_profile.profile.ngay_giao_ket;
  notes.push(
    assessed.moc_ap_dung
      ? `Quy định được chọn theo luật có hiệu lực tại ngày ${viDate(assessed.moc_ap_dung)} (mốc khai báo khi tải lên).`
      : signed
        ? `Không khai báo mốc áp dụng khi tải lên; hệ thống tự xác định mốc thời gian cho từng quy định (thường là ngày ký ${viDate(signed)}, đọc từ hợp đồng).`
        : "Không đọc được ngày ký trong hợp đồng, nên một số quy định chưa rõ có áp dụng hay không.",
  );
  return (
    <section className="panel notes" aria-label="Lưu ý về kết quả này">
      <h3>Lưu ý về kết quả này</h3>
      <ul>
        {notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </section>
  );
}
