import type {
  CitationExtraction,
  CitationValidation,
  ReportContent,
} from "../../../shared/api/client";
import { Empty, Fields, Section, StatusBadge, Value } from "../../../shared/components/ui";
import { displayText } from "../../../shared/text";
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
      title="Viện dẫn trong hợp đồng"
      description="C03 viện dẫn hợp đồng tự nêu và C09 kết quả xác minh tại ngày liên quan. Nhánh này không quyết định luật áp dụng; trạng thái hiện tại hiển thị riêng."
    >
      {citations.citations.length === 0 && <Empty>Hợp đồng không có viện dẫn được trích xuất.</Empty>}
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
  const pageText = (p: CitationExtraction["evidence"][number]) =>
    p.page_start === p.page_end ? `tr. ${p.page_start}` : `tr. ${p.page_start}–${p.page_end}`;
  const pages = citation.evidence.length
    ? citation.evidence.map((p, i) => (
        <span key={`${p.doan_id}-${i}`}>
          {i > 0 && ", "}
          {openEvidence ? (
            <button
              type="button"
              className="link"
              title={`Mở đoạn ${p.doan_id}`}
              onClick={() => openEvidence({ doanId: p.doan_id })}
            >
              {pageText(p)}
            </button>
          ) : (
            pageText(p)
          )}
        </span>
      ))
    : "không rõ trang";
  return (
    <article className="card-flat" id={focusDomId(citation.vien_dan_id)}>
      <header className="criterion-head">
        {findings.length === 0 ? (
          <span className="badge tone-unknown">Chưa có kết quả xác minh</span>
        ) : (
          findings.map((f) => <StatusBadge key={f.finding_id} kind="citation" code={f.status} />)
        )}
        <strong>{n.ten_van_ban ?? n.so_hieu ?? "Viện dẫn chưa chuẩn hóa được"}</strong>
        {article && <span>{article}</span>}
      </header>
      <blockquote className="raw">{displayText(citation.raw_text)}</blockquote>
      <p className="small muted">
        <code>{citation.vien_dan_id}</code> · {pages} ·{" "}
        <StatusBadge kind="extraction" code={citation.extraction.status} />
        {citation.extraction.confidence != null &&
          ` độ tin cậy ${Math.round(citation.extraction.confidence * 100)}%`}
      </p>
      <Fields
        rows={[
          ["Số hiệu", <Value value={n.so_hieu} />],
          ["Loại văn bản", <Value value={n.loai_van_ban} />],
          ["Ngày ban hành", <Value value={n.ngay_ban_hanh ?? n.nam} />],
        ]}
      />
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
  return (
    <div
      className={`finding${focus === finding.finding_id ? " focused" : ""}`}
      id={focusDomId(finding.finding_id)}
    >
      <div className="split">
        <div>
          <h4 className="minihead">Tại ngày liên quan {finding.relevant_date ?? "(chưa rõ)"}</h4>
          <StatusBadge kind="citation" code={finding.status} />{" "}
          <StatusBadge kind="domain" code={finding.domain_status} />{" "}
          {!finding.finding_verified && <span className="tag">chưa xác minh</span>}
        </div>
        <div>
          <h4 className="minihead">Trạng thái hiện tại (tham khảo)</h4>
          <Value value={finding.current_status} />
        </div>
      </div>
      <p>{finding.ly_do}</p>
      <dl className="fields compact">
        <div>
          <dt>Mã lý do</dt>
          <dd>
            <code>{finding.reason_code}</code>
          </dd>
        </div>
        <div>
          <dt>Văn bản chuẩn hóa</dt>
          <dd>
            <Value value={finding.normalized_van_ban_id} />
          </dd>
        </div>
        <div>
          <dt>Văn bản thay thế</dt>
          <dd>
            <Value value={finding.replacement_van_ban_id} />
          </dd>
        </div>
        <div>
          <dt>Knowledge</dt>
          <dd>
            <code>{finding.knowledge_version}</code>
          </dd>
        </div>
      </dl>
      {risks.length > 0 && (
        <div className="links">
          Rủi ro viện dẫn:{" "}
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
