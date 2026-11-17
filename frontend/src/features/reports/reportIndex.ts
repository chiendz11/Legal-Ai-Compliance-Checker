import { createContext, useContext } from "react";

import type {
  ApplicableRequirement,
  CitationExtraction,
  CitationValidation,
  CriterionResult,
  ProfileEvidence,
  Recommendation,
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
  recommendationsByRisk: Map<string, Recommendation[]>;
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
    recommendationsByRisk: groupBy(content.recommendations, (r) => r.ket_qua_rui_ro_id),
  };
}

export const ReportIndexContext = createContext<ReportIndex | null>(null);

export function useReportIndex() {
  const index = useContext(ReportIndexContext);
  if (!index) throw new Error("useReportIndex outside ReportPage");
  return index;
}

/** Human-readable criterion text from the knowledge snapshot pinned with the result. */
export function criterionSnapshot(criterion: CriterionResult): Record<string, unknown> {
  // Reference runs nest the knowledge row under "criterion"; module runs store it flat.
  const snapshot = (criterion.tieu_chi_snapshot_json ?? {}) as Record<string, unknown>;
  const nested = snapshot.criterion;
  return nested && typeof nested === "object" ? (nested as Record<string, unknown>) : snapshot;
}

export function criterionText(criterion: CriterionResult): string {
  const text = criterionSnapshot(criterion).noi_dung;
  return typeof text === "string" && text ? text : criterion.tieu_chi_id;
}

/** The pinned requirement version: "version" in reference runs, "requirement_version" in module runs. */
export function requirementVersion(
  requirement: RequirementResult,
): Record<string, unknown> | undefined {
  const snapshot = (requirement.requirement_snapshot_json ?? {}) as Record<string, unknown>;
  const version = snapshot.version ?? snapshot.requirement_version;
  return version && typeof version === "object" ? (version as Record<string, unknown>) : undefined;
}

/** Human-readable requirement text from the knowledge snapshot pinned with the result. */
export function requirementText(requirement: RequirementResult): string {
  const text = requirementVersion(requirement)?.noi_dung;
  return typeof text === "string" && text ? text : requirement.yeu_cau_ca_id;
}

export function riskTitle(risk: RiskResult): string {
  const snapshot = risk.risk_snapshot as { ten_rui_ro?: string; mo_ta?: string } | undefined;
  if (snapshot?.ten_rui_ro) return snapshot.ten_rui_ro;
  if (snapshot?.mo_ta) return snapshot.mo_ta;
  if (risk.rui_ro_id === "RR_CITATION_UNKNOWN") {
    return "Viện dẫn pháp lý chưa xác định rõ phiên bản hiệu lực";
  }
  if (risk.rui_ro_id.includes("VIOLATED")) {
    return "Phát hiện có dấu hiệu không tuân thủ quy định pháp luật";
  }
  if (risk.rui_ro_id.includes("UNKNOWN")) {
    return "Cần xác minh và làm rõ điều khoản hợp đồng";
  }
  return risk.rui_ro_id;
}

/** requirement_id → plain-language name and topic, from the report's pinned knowledge snapshot. */
export type RequirementInfo = { title: string; group: string | null };
export const RequirementNamesContext = createContext<Map<string, RequirementInfo>>(new Map());

export function useRequirementName() {
  const names = useContext(RequirementNamesContext);
  return (requirementId: string | null | undefined) =>
    (requirementId && names.get(requirementId)?.title) || null;
}

export function useRequirementGroup() {
  const names = useContext(RequirementNamesContext);
  return (requirementId: string | null | undefined) =>
    (requirementId && names.get(requirementId)?.group) || null;
}

/** requirement_id of a per-case requirement row (yeu_cau_ca_id = <ca_id>_<requirement_id>). */
export function requirementIdOf(index: ReportIndex, yeuCauCaId: string): string | null {
  return index.applicableById.get(yeuCauCaId)?.requirement_id ?? null;
}
