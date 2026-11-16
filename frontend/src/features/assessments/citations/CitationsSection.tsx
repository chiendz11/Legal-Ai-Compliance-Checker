import type {
  CitationExtraction,
  CitationValidation,
  ReportContent,
} from "../../../shared/api/client";
import { Empty, Section, StatusBadge } from "../../../shared/components/ui";
import { label } from "../../../shared/labels";
import { displayText } from "../../../shared/text";
import { CitationDistribution } from "../../reports/distributions";
import { viDate } from "../../reports/explain";
import { LegalBasis } from "../../reports/legalBasis";
import { focusDomId, useReportNav } from "../../reports/nav";
import { riskTitle, useReportIndex } from "../../reports/reportIndex";
import { useOpenEvidence } from "../evidence/EvidenceViewer";

export function CitationsSection({
  citations,
}: {
  citations: ReportContent["citation_validation"];
}) {
  const findingsByCitation = new Map<string, CitationValidation[]>();
  for (const f of citations.findings) {
    findingsByCitation.set(f.vien_dan_id, [...(findingsByCitation.get(f.vien_dan_id) ?? []), f]);
  }
  const extracted = new Set(citations.citations.map((c) => c.vien_dan_id));
  const orphanFindings = citations.findings.filter((f) => !extracted.has(f.vien_dan_id));

  return (
    <Section
      title="Luật hợp đồng trích dẫn"
      description="Các văn bản luật mà chính hợp đồng nhắc tới, được đối chiếu với kho văn bản pháp luật: còn hiệu lực tại ngày ký hay không, có bị thay thế không. Phần này chỉ kiểm tra trích dẫn của hợp đồng, không quyết định quy định nào áp dụng."
    >
      {citations.citations.length === 0 && <Empty>Không đọc được văn bản luật nào mà hợp đồng trích dẫn.</Empty>}
      {citations.findings.length > 0 && <CitationDistribution findings={citations.findings} />}
      <div className="stack">
        {citations.citations.map((c) => (
          <CitationCard
            key={c.vien_dan_id}
            citation={c}
            findings={findingsByCitation.get(c.vien_dan_id) ?? []}
          />
        ))}
        {orphanFindings.map((f) => (
          <FindingBlock key={f.finding_id} finding={f} />
        ))}
      </div>
    </Section>
  );
}

/** Today's status of the cited document, in words (reference only; the verdict is at signing). */
const CURRENT_STATUS: Record<string, string> = {
  HISTORICAL: "Hiện nay văn bản này đã hết hiệu lực (đã có văn bản thay thế).",
  HISTORICAL_CAN_XAC_MINH_NGAY_HET_HIEU_LUC:
    "Hiện nay văn bản này đã hết hiệu lực; ngày hết hiệu lực cần xác minh thêm.",
  CURRENT: "Hiện nay văn bản này vẫn còn hiệu lực.",
  IN_FORCE: "Hiện nay văn bản này vẫn còn hiệu lực.",
};

function currentStatus(code: string | null | undefined): string | null {
  if (!code) return null;
  if (CURRENT_STATUS[code]) return CURRENT_STATUS[code];
  const known = label("docStatus", code).text;
  return known !== code ? `Hiện trạng văn bản: ${known.toLowerCase()}.` : null;
}

function CitationCard({
  citation,
  findings,
}: {
  citation: CitationExtraction;
  findings: CitationValidation[];
}) {
  const n = citation.normalized;
  const article = [n.dieu && `Điều ${n.dieu}`, n.khoan && `khoản ${n.khoan}`]
    .filter(Boolean)
    .join(" ");
  const openEvidence = useOpenEvidence();
  const first = citation.evidence[0];
  const pages = [...new Set(citation.evidence.map((p) => p.page_start))];
  const facts = [
    n.so_hieu ? `Số hiệu ${n.so_hieu}` : "Không ghi số hiệu",
    n.loai_van_ban,
    n.ngay_ban_hanh ? `ban hành ${viDate(n.ngay_ban_hanh)}` : n.nam ? `năm ${n.nam}` : null,
  ].filter(Boolean);
  return (
    <article className="card-flat citation" id={focusDomId(citation.vien_dan_id)} title={citation.vien_dan_id}>
      <header className="criterion-head">
        {findings.length === 0 ? (
          <span className="badge tone-unknown">Chưa đối chiếu</span>
        ) : (
          findings.map((f) => <StatusBadge key={f.finding_id} kind="citation" code={f.status} />)
        )}
        <strong>{n.ten_van_ban ?? n.so_hieu ?? "Văn bản chưa xác định được tên"}</strong>
        {article && <span>{article}</span>}
      </header>
      <p className="muted small">{facts.join(" · ")}</p>
      <blockquote className="raw">“{displayText(citation.raw_text)}”</blockquote>
      {first && (
        <p className="small">
          {openEvidence ? (
            <button
              type="button"
              className="link"
              onClick={() => openEvidence({ doanId: first.doan_id, quote: citation.raw_text })}
            >
              Xem trong hợp đồng (trang {pages.join(", ")})
            </button>
          ) : (
            <span className="muted">Trang {pages.join(", ")} của hợp đồng</span>
          )}
        </p>
      )}
      {findings.map((f) => (
        <FindingBlock key={f.finding_id} finding={f} />
      ))}
    </article>
  );
}

function FindingBlock({ finding }: { finding: CitationValidation }) {
  const index = useReportIndex();
  const { focus, go } = useReportNav();
  const risks = index.risksByFinding.get(finding.finding_id) ?? [];
  const current = currentStatus(finding.current_status);
  return (
    <div
      className={`finding${focus === finding.finding_id ? " focused" : ""}`}
      id={focusDomId(finding.finding_id)}
      title={`${finding.reason_code} · ${finding.knowledge_version}`}
    >
      <p className="finding-verdict">
        <strong>
          {finding.relevant_date ? `Tại ngày ký ${viDate(finding.relevant_date)}: ` : "Kết quả: "}
        </strong>
        {finding.ly_do}
      </p>
      {finding.domain_status === "MISMATCH" && (
        <p className="uncertain small">Văn bản này không thuộc lĩnh vực của hợp đồng.</p>
      )}
      {current && <p className="small muted">{current}</p>}
      {finding.replacement_van_ban_id && (
        <p className="small">
          <span className="muted">Văn bản thay thế: </span>
          <LegalBasis ids={[finding.replacement_van_ban_id]} />
        </p>
      )}
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
    </div>
  );
}
