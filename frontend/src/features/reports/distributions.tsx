import type { CitationValidation, RequirementResult } from "../../shared/api/client";
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

export function RequirementDistribution({ results }: { results: RequirementResult[] }) {
  return (
    <Distribution
      title="Kết luận theo quy định"
      description="Số quy định theo từng kết luận. Hệ thống không quy đổi thành điểm số tuân thủ."
      unit="quy định"
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
      description="Số luật hợp đồng trích dẫn theo kết quả đối chiếu tại ngày ký."
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
