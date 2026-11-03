import type {
  CitationValidation,
  ReportContent,
  RequirementResult,
} from "../../shared/api/client";
import { Distribution, STATUS_COLORS as S } from "../../shared/components/Distribution";
import { label, type LabelKind } from "../../shared/labels";

/** Fixed order and color per stored status; counts come straight from the report. */
function items(kind: LabelKind, order: [string, string][], codes: string[]) {
  return order.map(([code, color]) => ({
    key: code,
    label: label(kind, code).text,
    count: codes.filter((c) => c === code).length,
    color,
  }));
}

export function RiskDistribution({ risks }: { risks: ReportContent["risks"] }) {
  const all = [...risks.compliance, ...risks.citation, ...risks.verification];
  return (
    <Distribution
      title="Phân bổ mức độ rủi ro"
      description="Số rủi ro C10 theo mức độ do Risk Engine gán. “Cần review” là rủi ro chưa đủ căn cứ để xếp mức."
      unit="rủi ro"
      items={items(
        "severity",
        [
          ["CRITICAL", S.critical],
          ["HIGH", S.serious],
          ["MEDIUM", S.warning],
          ["LOW", S.good],
          ["REVIEW_REQUIRED", S.none],
        ],
        all.map((r) => r.severity),
      )}
    />
  );
}

export function RequirementDistribution({ results }: { results: RequirementResult[] }) {
  return (
    <Distribution
      title="Phân bổ kết luận yêu cầu"
      description="Số yêu cầu C08 theo trạng thái backend tổng hợp. Không quy đổi thành điểm tuân thủ."
      unit="yêu cầu"
      items={items(
        "requirement",
        [
          ["NON_COMPLIANT", S.critical],
          ["PARTIAL", S.warning],
          ["COMPLIANT", S.good],
          ["INSUFFICIENT", S.none],
        ],
        results.map((r) => r.status),
      )}
    />
  );
}

export function CitationDistribution({ findings }: { findings: CitationValidation[] }) {
  return (
    <Distribution
      title="Phân bổ kết quả xác minh viện dẫn"
      description="Số viện dẫn C09 theo trạng thái tại ngày liên quan."
      unit="viện dẫn"
      items={items(
        "citation",
        [
          ["INVALID", S.critical],
          ["STALE", S.warning],
          ["VALID", S.good],
          ["UNKNOWN", S.none],
        ],
        findings.map((f) => f.status),
      )}
    />
  );
}
