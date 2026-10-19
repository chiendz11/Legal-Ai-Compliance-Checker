import { createContext, useContext } from "react";

import type {
  ApplicableRequirement,
  CitationExtraction,
  CitationValidation,
  CriterionResult,
  ProfileEvidence,
  ReportContent,
  RequirementResult,
  RiskResult,
} from "../../shared/api/client";

/** Lookups by ID so sections can link risk → finding → evidence without re-joining data. */
export type ReportIndex = {
  requirementById: Map<string, RequirementResult>;
  applicableById: Map<string, ApplicableRequirement>;
  criteriaByRequirement: Map<string, CriterionResult[]>;
  criterionById: Map<string, CriterionResult>;
  citationById: Map<string, CitationExtraction>;
  findingById: Map<string, CitationValidation>;
  risksByCriterion: Map<string, RiskResult[]>;
  risksByFinding: Map<string, RiskResult[]>;
  profileEvidenceById: Map<string, ProfileEvidence>;
};

function groupBy<T>(items: T[], key: (item: T) => string | null | undefined) {
  const map = new Map<string, T[]>();
  for (const item of items) {
    const k = key(item);
    if (k == null) continue;
    map.set(k, [...(map.get(k) ?? []), item]);
  }
  return map;
}

export function buildIndex(content: ReportContent): ReportIndex {
  const risks = [
    ...content.risks.compliance,
    ...content.risks.citation,
    ...content.risks.verification,
  ];
  return {
    requirementById: new Map(
      content.compliance.requirement_results.map((r) => [r.yeu_cau_ca_id, r]),
    ),
    applicableById: new Map(content.applicable_legal_scope.map((r) => [r.yeu_cau_ca_id, r])),
    criteriaByRequirement: groupBy(content.compliance.criterion_results, (c) => c.yeu_cau_ca_id),
    criterionById: new Map(content.compliance.criterion_results.map((c) => [c.ket_qua_id, c])),
    citationById: new Map(content.citation_validation.citations.map((c) => [c.vien_dan_id, c])),
    findingById: new Map(content.citation_validation.findings.map((f) => [f.finding_id, f])),
    risksByCriterion: groupBy(risks, (r) => r.source.ket_qua_tieu_chi_id),
    risksByFinding: groupBy(risks, (r) => r.source.citation_finding_id),
    profileEvidenceById: new Map(
      (content.contract_profile.evidence ?? []).map((e) => [e.bang_chung_id, e]),
    ),
  };
}

export const ReportIndexContext = createContext<ReportIndex | null>(null);

export function useReportIndex() {
  const index = useContext(ReportIndexContext);
  if (!index) throw new Error("useReportIndex outside ReportPage");
  return index;
}

/** Human-readable criterion text from the knowledge snapshot pinned with the result. */
export function criterionText(criterion: CriterionResult): string {
  const snapshot = criterion.tieu_chi_snapshot_json as { criterion?: { noi_dung?: string } };
  return snapshot.criterion?.noi_dung ?? criterion.tieu_chi_id;
}

export function requirementText(requirement: RequirementResult): string {
  const snapshot = requirement.requirement_snapshot_json as { version?: { noi_dung?: string } };
  return snapshot.version?.noi_dung ?? requirement.yeu_cau_ca_id;
}

export function riskTitle(risk: RiskResult): string {
  const snapshot = risk.risk_snapshot as { ten_rui_ro?: string };
  return snapshot.ten_rui_ro ?? risk.rui_ro_id;
}
