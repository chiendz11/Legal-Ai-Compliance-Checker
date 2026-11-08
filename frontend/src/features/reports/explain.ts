/**
 * Plain-language reasons for the report screens.
 *
 * The modules record their reasoning as technical traces ("UNKNOWN: loai_chu_the=…; party
 * capacity not confirmed", "marker type unverified for every version of this family"). A reader
 * outside the team needs the cause in one Vietnamese sentence and what kind of problem it is
 * (missing contract facts vs. an unfinished legal catalogue vs. AI not run). This only reads the
 * stored statuses and reasons; it never changes a status. The raw trace stays one click away.
 */
import type {
  ApplicableRequirement,
  CriterionResult,
  RequirementResult,
} from "../../shared/api/client";
import { fieldLabel } from "../../shared/fieldLabels";
import { label } from "../../shared/labels";

export type Cause =
  | "APPLIES"
  | "NOT_APPLICABLE"
  | "PARTY"
  | "MISSING_FACT"
  | "MARKER"
  | "DATE"
  | "NO_AI"
  | "AI_PENDING"
  | "NO_EVIDENCE"
  | "DONE"
  | "OTHER";

/** Title and what to do, for the summary panel. */
export const CAUSES: Record<Cause, { title: string; hint: string }> = {
  APPLIES: { title: "Có áp dụng", hint: "" },
  NOT_APPLICABLE: { title: "Không áp dụng cho hợp đồng này", hint: "" },
  PARTY: {
    title: "Chưa xác nhận được tư cách các bên",
    hint: "Hợp đồng chưa cho thấy rõ bên bán là doanh nghiệp kinh doanh bất động sản hay chủ đầu tư. Cần bổ sung hồ sơ bên bán hoặc người duyệt xác nhận.",
  },
  MISSING_FACT: {
    title: "Hợp đồng thiếu thông tin cần thiết",
    hint: "Hệ thống không tìm thấy các thông tin này trong hợp đồng nên chưa biết quy định có áp dụng không.",
  },
  MARKER: {
    title: "Kho tri thức pháp lý chưa chốt mốc thời gian",
    hint: "Chưa xác định quy định tính theo ngày ký, ngày thu tiền hay ngày bàn giao, nên chưa chọn được điều luật. Đây là việc của nhóm dữ liệu pháp lý, không phải lỗi của hợp đồng.",
  },
  DATE: {
    title: "Hợp đồng không ghi ngày cần thiết",
    hint: "Thiếu ngày làm mốc (ví dụ ngày thu tiền) để biết điều luật nào đang có hiệu lực.",
  },
  NO_AI: {
    title: "Chưa chạy AI đánh giá nội dung",
    hint: "Lần chạy này không gọi AI (hoặc đã hết lượt gọi), nên các điểm kiểm tra còn “chưa xác định”. Bật AI rồi chạy lại.",
  },
  AI_PENDING: {
    title: "AI đã đọc nhưng chưa đủ căn cứ kết luận",
    hint: "AI đã đọc các đoạn hợp đồng liên quan nhưng chưa kết luận được, hoặc kết luận cần một dữ kiện chưa được xác minh. Lý do ghi ở từng quy định; chuyên viên có thể xác nhận ở mục Rà soát.",
  },
  NO_EVIDENCE: {
    title: "Không tìm thấy đoạn hợp đồng liên quan",
    hint: "Bước tìm bằng chứng chưa chọn được đoạn nào trong hợp đồng cho quy định này.",
  },
  DONE: { title: "Đã đánh giá", hint: "" },
  OTHER: { title: "Lý do khác", hint: "Xem chi tiết kỹ thuật trong từng quy định." },
};

export type Explanation = { cause: Cause; text: string; fields?: string[] };

/** 2024-08-01 → 01/08/2024 */
export function viDate(iso: string | null | undefined): string {
  const m = iso?.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : (iso ?? "");
}

function markerName(code: string | null | undefined): string {
  return code ? label("markerType", code).text.toLowerCase() : "";
}

// "field=None vs EQ …" and "any(field)=[None, None] vs ANY […]" both mean the contract lacks it.
const MISSING_FIELD = /\b(?:any\()?([a-z][a-z_]+)\)?=\[?None\b/g;

function missingFields(reason: string): string[] {
  return [...new Set([...reason.matchAll(MISSING_FIELD)].map((m) => m[1] ?? ""))].filter(Boolean);
}

function reasonParts(a: ApplicableRequirement) {
  const reason = (a.reason ?? {}) as Record<string, unknown>;
  return {
    scope: typeof reason.scope === "string" ? reason.scope : "",
    version: typeof reason.version === "string" ? reason.version : "",
  };
}

/** Why a requirement does / does not / may apply to this contract. */
export function explainApplicable(a: ApplicableRequirement): Explanation {
  const { scope, version } = reasonParts(a);
  if (a.applicability_status === "CONFIRMED") {
    return {
      cause: "APPLIES",
      text:
        a.loai_moc && a.moc_ap_dung
          ? `Áp dụng: điều luật đang có hiệu lực tại ngày ${markerName(a.loai_moc)} ${viDate(a.moc_ap_dung)}.`
          : "Áp dụng cho hợp đồng này.",
    };
  }
  if (a.applicability_status === "NOT_APPLICABLE") {
    if (a.scope_status === "NO_MATCH")
      return { cause: "NOT_APPLICABLE", text: "Không dành cho loại hợp đồng hoặc giao dịch này." };
    const later = version.match(/introduced on (\d{4}-\d{2}-\d{2}), after (\d{4}-\d{2}-\d{2})/);
    if (later)
      return {
        cause: "NOT_APPLICABLE",
        text: `Quy định này có hiệu lực từ ${viDate(later[1])}, sau ngày ${markerName(a.loai_moc) || "làm mốc"} ${viDate(later[2])} của hợp đồng, nên không áp dụng.`,
      };
    return { cause: "NOT_APPLICABLE", text: "Không áp dụng cho hợp đồng này." };
  }
  if (a.scope_status === "UNKNOWN") {
    const fields = missingFields(scope).filter((f) => f !== "loai_chu_the");
    if (/party capacity not confirmed/i.test(scope)) {
      const extra = fields.length ? ` Thiếu thêm: ${fields.map(fieldLabel).join(", ")}.` : "";
      return {
        cause: "PARTY",
        text: `Chưa xác nhận được tư cách các bên (bên bán có phải doanh nghiệp kinh doanh bất động sản, chủ đầu tư hay không).${extra}`,
        fields,
      };
    }
    if (fields.length) {
      const notExtracted = /profile has no field/i.test(scope)
        ? " Hệ thống hiện chưa đọc loại thông tin này từ hợp đồng."
        : "";
      return {
        cause: "MISSING_FACT",
        text: `Chưa biết có áp dụng không vì hợp đồng chưa cho biết: ${fields.map(fieldLabel).join(", ")}.${notExtracted}`,
        fields,
      };
    }
    return { cause: "OTHER", text: "Chưa xác định được quy định này có dành cho hợp đồng này không." };
  }
  if (a.version_status === "UNKNOWN") {
    if (/marker type unverified/i.test(version))
      return {
        cause: "MARKER",
        text: "Kho tri thức chưa xác định quy định này tính theo mốc thời gian nào, nên chưa chọn được điều luật có hiệu lực.",
      };
    const date = version.match(/\b([A-Z_]+) date unknown/);
    if (date)
      return {
        cause: "DATE",
        text: `Hợp đồng không ghi rõ ngày ${markerName(date[1])}, nên chưa biết điều luật nào đang có hiệu lực.`,
      };
  }
  return { cause: "OTHER", text: "Chưa xác nhận được quy định này có áp dụng hay không." };
}

const AI_NOT_CALLED = "NO_LLM_CALL";

function noted(criteria: CriterionResult[], pattern: RegExp) {
  return criteria.some((c) => pattern.test(c.uncertainty_reason ?? ""));
}

/** Criteria with a real finding; the backend's "evaluated" count also includes UNKNOWN ones. */
export function concludedCount(requirement: RequirementResult): number {
  return Math.max(0, requirement.so_tieu_chi_da_danh_gia - requirement.so_unknown);
}

/** One sentence for a requirement row: the result, or the first reason it has none. */
export function explainRequirement(
  requirement: RequirementResult,
  applicable: ApplicableRequirement | undefined,
  criteria: CriterionResult[],
): Explanation {
  if (requirement.status !== "INSUFFICIENT")
    return {
      cause: "DONE",
      text: `${label("requirement", requirement.status).text} (${concludedCount(requirement)}/${requirement.so_tieu_chi_ap_dung} điểm kiểm tra có kết luận).`,
    };
  if (applicable && applicable.applicability_status !== "CONFIRMED") {
    const why = explainApplicable(applicable);
    // An unrecognised scope trace says little; the criteria may name a clearer cause.
    if (why.cause !== "OTHER" || criteria.length === 0) return why;
  }
  if (criteria.length === 0)
    return { cause: "OTHER", text: "Chưa có điểm kiểm tra nào cho quy định này." };
  const read = criteria.find((c) => c.model_version !== AI_NOT_CALLED);
  if (read)
    return {
      cause: "AI_PENDING",
      text: explainCriterion(read) ?? "AI đã đọc hợp đồng nhưng chưa đủ căn cứ để kết luận.",
    };
  if (noted(criteria, /offline/i))
    return { cause: "NO_AI", text: "Chưa chạy AI để đọc và đánh giá nội dung hợp đồng." };
  if (noted(criteria, /giới hạn|CALL_LIMIT/i))
    return { cause: "NO_AI", text: "AI chưa được gọi cho quy định này (đã hết lượt gọi của lần chạy)." };
  if (noted(criteria, /selected FINAL/i))
    return { cause: "NO_EVIDENCE", text: "Không tìm thấy đoạn hợp đồng liên quan để kiểm tra." };
  return { cause: "OTHER", text: "Chưa đủ bằng chứng để kết luận." };
}

// Sentences written by the engine for engineers, not for readers.
const ENGINE_TRACE =
  /Cannot accept a finding|Unresolved gate|Provider uncertainty|Requirement applicability|Criterion (?:local_applicability|requires)|^(?:INSUFFICIENT|UNKNOWN):|\b[a-z]+_[a-z_]+=/;
const DRAFT_MARK = /^\s*\[MACHINE_DRAFT_REVIEW\]\s*/;

/**
 * One Vietnamese sentence for a stored machine explanation (criterion result, review card).
 * Text a person or the AI wrote in Vietnamese is kept; engine traces are translated by their
 * first, most basic cause. The raw text stays available under "chi tiết kỹ thuật".
 */
export function readableReason(text: string | null | undefined): string | null {
  const raw = (text ?? "").trim();
  if (!raw) return null;
  if (!ENGINE_TRACE.test(raw)) return raw.replace(DRAFT_MARK, "");
  if (/applicability\/scope\/version is not confirmed/i.test(raw))
    return "Chưa kết luận vì chưa xác nhận quy định này áp dụng cho hợp đồng (hợp đồng chưa cho biết đủ thông tin về các bên hoặc loại giao dịch). Lý do cụ thể ghi ở quy định.";
  if (/offline|NO_LLM_CALL/i.test(raw)) return "Chưa chạy AI để đọc nội dung hợp đồng.";
  if (/giới hạn số criterion|CALL_LIMIT/i.test(raw)) return "Đã hết lượt gọi AI trong lần chạy này.";
  if (/selected FINAL/i.test(raw)) return "Không tìm thấy đoạn hợp đồng liên quan để kiểm tra.";
  if (/QUOTE_(?:OFFSET_)?MISMATCH|AMBIGUOUS_QUOTE/.test(raw))
    return "AI đưa trích dẫn không khớp nguyên văn hợp đồng nên kết luận bị loại.";
  const ai = raw.match(/Semantic predicate has not been reviewed:\s*([^;]+)/);
  if (ai?.[1]) return `AI chưa kết luận được: ${ai[1].trim().replace(/\.?$/, ".")}`;
  if (/AI còn liệt kê điều kiện chưa rõ/.test(raw))
    return "AI còn nêu điều kiện chưa rõ nên chưa kết luận.";
  if (/case facts|local_applicability/i.test(raw))
    return "Điểm kiểm tra này chỉ áp dụng khi có điều kiện phát sinh cụ thể; điều kiện đó chưa được xác minh nên kết luận của AI chưa được chấp nhận.";
  if (/^INSUFFICIENT/.test(raw)) return "Chưa đủ căn cứ: các điểm kiểm tra bắt buộc chưa có kết luận.";
  return "Chưa đủ căn cứ để kết luận.";
}

/** Short reason under one criterion, instead of the raw module trace. */
export function explainCriterion(c: CriterionResult): string | null {
  if (c.finding !== "UNKNOWN") return null;
  const reason = c.uncertainty_reason ?? "";
  if (c.model_version === AI_NOT_CALLED && /offline/i.test(reason)) return "Chưa chạy AI.";
  return readableReason(reason) ?? "Chưa đủ căn cứ để kết luận.";
}

/** How many criteria actually went to the AI in this run. */
export function aiUsage(criteria: CriterionResult[]) {
  return {
    total: criteria.length,
    called: criteria.filter((c) => c.model_version !== AI_NOT_CALLED).length,
  };
}
