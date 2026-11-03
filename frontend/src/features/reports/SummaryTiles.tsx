import type { ReportContent } from "../../shared/api/client";
import { label, type LabelKind } from "../../shared/labels";

function count<T>(items: T[], key: (item: T) => string) {
  const map = new Map<string, number>();
  for (const item of items) map.set(key(item), (map.get(key(item)) ?? 0) + 1);
  return map;
}

/**
 * Counts and coverage straight from the lists, with no single compliance score:
 * a score formula has not been agreed, and UNKNOWN/INSUFFICIENT must stay visible.
 */
export function SummaryTiles({ content }: { content: ReportContent }) {
  const { compliance, citation_validation, risks, recommendations } = content;
  return (
    <div className="tiles">
      <Tile
        title="Yêu cầu"
        total={compliance.requirement_results.length}
        kind="requirement"
        counts={count(compliance.requirement_results, (r) => r.status)}
        note={`${content.applicable_legal_scope.length} yêu cầu trong phạm vi`}
      />
      <Tile
        title="Tiêu chí"
        total={compliance.criterion_results.length}
        kind="criterion"
        counts={count(compliance.criterion_results, (c) => c.finding)}
      />
      <Tile
        title="Viện dẫn"
        total={citation_validation.findings.length}
        kind="citation"
        counts={count(citation_validation.findings, (f) => f.status)}
        note={`${citation_validation.citations.length} viện dẫn trích xuất`}
      />
      <Tile
        title="Rủi ro"
        total={risks.compliance.length + risks.citation.length + risks.verification.length}
        kind="riskType"
        counts={
          new Map([
            ["COMPLIANCE", risks.compliance.length],
            ["CITATION", risks.citation.length],
            ["VERIFICATION", risks.verification.length],
          ])
        }
        note={`${recommendations.length} khuyến nghị`}
      />
    </div>
  );
}

function Tile({
  title,
  total,
  kind,
  counts,
  note,
}: {
  title: string;
  total: number;
  kind: LabelKind;
  counts: Map<string, number>;
  note?: string;
}) {
  return (
    <div className="tile">
      <div className="tile-head">
        <span>{title}</span>
        <strong>{total}</strong>
      </div>
      <ul>
        {[...counts].map(([code, n]) => {
          const { text, tone } = label(kind, code);
          return (
            <li key={code}>
              <span className={`dot tone-${tone}`} aria-hidden />
              <span>{text}</span>
              <span className="num">{n}</span>
            </li>
          );
        })}
      </ul>
      {note && <p className="muted small">{note}</p>}
    </div>
  );
}
