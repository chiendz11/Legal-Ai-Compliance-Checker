import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

/** Same-origin client: Vite proxies /api and /health to the backend; MSW mocks planned routes. */
export const api = createClient<paths>({ baseUrl: "" });

type Schemas = components["schemas"];
export type CaseRecord = Schemas["Output_CaseRecord"];
export type AssessmentCase = Schemas["Output_AssessmentCase"];
export type ReportRecord = Schemas["Output_ReportRecord"];
export type FinalReport = Schemas["Output_FinalReport"];
export type ReportContent = Schemas["Output_ReportContent"];
export type ContractProfile = Schemas["Output_ContractProfile"];
export type ProfileEvidence = Schemas["Output_ProfileEvidence"];
export type ApplicableRequirement = Schemas["Output_ApplicableRequirement"];
export type ScopeResolution = Schemas["Output_ScopeResolution"];
export type RequirementResult = Schemas["Output_RequirementResult"];
export type CriterionResult = Schemas["Output_CriterionResult"];
export type Evidence = Schemas["Output_Evidence"];
export type CitationExtraction = Schemas["Output_CitationExtraction"];
export type CitationValidation = Schemas["Output_CitationValidation"];
export type RiskResult = Schemas["Output_RiskResult"];
export type Recommendation = Schemas["Output_Recommendation"];
export type LegalBasisItem = Schemas["Output_LegalBasisItem"];
export type AssessmentDraft = Schemas["Output_AssessmentDraft"];
export type Chunk = Schemas["Output_Chunk"];
export type Page<T> = { items: T[]; page: number; page_size: number; total: number };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`API ${status}`);
  }
}

/** Unwrap an openapi-fetch result, turning error responses into ApiError for React Query. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined) throw new ApiError(result.response.status, result.error);
  return result.data;
}
