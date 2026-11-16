import type { CriterionResult, RequirementResult } from "../../shared/api/client";
import type { ReportRecord } from "../../shared/api/client";
import { createContext, useContext } from "react";

export type ReportPresentation = NonNullable<ReportRecord["presentation"]>;
export const ReportPresentationContext = createContext<ReportPresentation | null>(null);
export const useReportPresentation = () => useContext(ReportPresentationContext);

/** Stored operational metadata; the original legal status is retained in C08. */
export function requirementDisplayStatus(row: RequirementResult): string {
  const disposition = row.requirement_snapshot_json.assessment_disposition;
  return disposition === "NOT_TRIGGERED" || disposition === "OUTSIDE_REVIEW_SCOPE"
    ? disposition : row.status;
}
export function criterionDisplayStatus(row: CriterionResult): string {
  return row.excluded && row.exclusion_reason?.startsWith("REVIEW_SCOPE_EXCLUDED:")
    ? "OUTSIDE_REVIEW_SCOPE" : row.excluded ? "EXCLUDED" : row.finding;
}
