import { createContext, useContext } from "react";

import requirementsCatalog from "../../shared/requirements_catalog.json";
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

/** Standard Vietnamese names for obligation families */
export const REQUIREMENT_FAMILY_LABELS: Record<string, string> = {
  FAM_APARTMENT_DESCRIPTION: "Mô tả đặc điểm căn hộ & diện tích sở hữu",
  FAM_APT_AREA_NET: "Diện tích sử dụng căn hộ (kích thước thông thủy)",
  FAM_APT_CERTIFICATE_50D: "Thủ tục cấp Giấy chứng nhận quyền sở hữu (50 ngày)",
  FAM_APT_COMMERCIAL_CONTENT: "Nội dung hợp đồng mua bán căn hộ thương mại",
  FAM_APT_COMMON_PRIVATE: "Phân định phần sở hữu chung và sở hữu riêng",
  FAM_APT_DEPOSIT: "Quy định đặt cọc mua bán căn hộ (tối đa 5%)",
  FAM_APT_EFFECTIVE_SIGNING: "Thời điểm ký kết và hiệu lực hợp đồng",
  FAM_APT_GUARANTEE_ACCEPT: "Cam kết phát hành bảo lãnh ngân hàng của chủ đầu tư",
  FAM_APT_GUARANTEE_CHOICE: "Thỏa thuận bằng văn bản về việc không bảo lãnh",
  FAM_APT_GUARANTEE_LETTER: "Nghĩa vụ cung cấp thư bảo lãnh ngân hàng",
  FAM_APT_HOUSING_CONTENT: "Nội dung hợp đồng theo quy định Luật Nhà ở",
  FAM_APT_MAINTENANCE_ACCOUNT: "Tài khoản kinh phí bảo trì căn hộ 2%",
  FAM_APT_PARKING: "Quy định về chỗ để xe và sở hữu chỗ để xe",
  FAM_APT_RESALE_NOTARY: "Công chứng hợp đồng chuyển nhượng căn hộ",
  FAM_APT_SOCIAL_RESALE: "Điều kiện chuyển nhượng, bán lại nhà ở xã hội",
  FAM_APT_WARRANTY_ORIGIN: "Thời hạn và trách nhiệm bảo hành nhà chung cư",
  FAM_BREACH_LIABILITY: "Trách nhiệm do vi phạm nghĩa vụ hợp đồng",
  FAM_CONTRACT_CLARITY: "Tính rõ ràng, minh bạch của điều khoản",
  FAM_CONTRACT_LANGUAGE: "Ngôn ngữ hợp đồng giao kết bằng tiếng Việt",
  FAM_DISPUTE_KDBDS: "Phương thức giải quyết tranh chấp kinh doanh BĐS",
  FAM_DISPUTE__KDBDS: "Phương thức giải quyết tranh chấp kinh doanh BĐS",
  FAM_DS418: "Thỏa thuận phạt vi phạm hợp đồng (Bộ luật Dân sự)",
  FAM_DS431: "Đối tượng và quyền bán tài sản",
  FAM_DS432: "Chất lượng tài sản giao dịch",
  FAM_DS433: "Giá mua bán và phương thức thanh toán",
  FAM_DS434: "Thời hạn giao tài sản và thanh toán",
  FAM_DS435: "Địa điểm giao nhận tài sản",
  FAM_DS436: "Phương thức giao nhận tài sản",
  FAM_DS437: "Quy định về số lượng tài sản giao kết",
  FAM_DS438: "Tính đồng bộ của vật mua bán",
  FAM_DS439: "Chủng loại tài sản giao kết",
  FAM_DS440: "Nghĩa vụ trả tiền mua bán tài sản",
  FAM_DS441: "Thời điểm chuyển giao rủi ro đối với tài sản",
  FAM_DS442: "Chi phí vận chuyển và chuyển quyền sở hữu",
  FAM_DS443: "Cung cấp thông tin và hướng dẫn sử dụng tài sản",
  FAM_DS444: "Bảo đảm quyền sở hữu của bên mua",
  FAM_DS445: "Bảo đảm chất lượng vật bán",
  FAM_DS446: "Điều kiện và thời hạn bảo hành tài sản",
  FAM_DS447: "Quyền yêu cầu sửa chữa, bảo hành",
  FAM_DS448: "Chi phí sửa chữa trong thời gian bảo hành",
  FAM_DS449: "Bồi thường thiệt hại trong thời hạn bảo hành",
  FAM_DS452: "Mua tài sản sau khi dùng thử",
  FAM_DS453: "Mua tài sản trả chậm hoặc trả dần",
  FAM_EFFECTIVE_TIME__KDBDS: "Thời điểm có hiệu lực của hợp đồng (KDBĐS)",
  FAM_EFFECTIVE_TIME__NHAO: "Thời điểm có hiệu lực của hợp đồng (Luật Nhà ở)",
  FAM_FIRST_PAYMENT_CAP: "Mức thu lần đầu không vượt quá 30% giá trị hợp đồng",
  FAM_FUTURE_PROPERTY_ELIGIBILITY_NOTICE: "Thông báo đủ điều kiện bán nhà ở hình thành trong tương lai",
  FAM_FUTURE_PROPERTY_GUARANTEE: "Bảo lãnh ngân hàng trong bán nhà ở hình thành trong tương lai",
  FAM_FUTURE_PROPERTY_GUARANTEE_COPY: "Cung cấp bản sao thư bảo lãnh ngân hàng cho bên mua",
  FAM_FUTURE_PROPERTY_LEGAL_DOCS: "Hồ sơ pháp lý dự án nhà ở hình thành trong tương lai",
  FAM_GENERAL_TERMS_DISCLOSURE: "Công khai điều kiện giao dịch chung",
  FAM_GYC048: "Đăng ký hợp đồng theo mẫu, điều kiện giao dịch chung",
  FAM_HANDOVER: "Thời hạn và hồ sơ bàn giao bất động sản",
  FAM_HANDOVER_WARRANTY_TIME: "Thời gian giao nhận và bảo hành nhà ở mới",
  FAM_INTERPRET_CONSUMER_FAVOR: "Giải thích hợp đồng theo hướng có lợi cho người tiêu dùng",
  FAM_MAINTENANCE_2_PERCENT: "Kinh phí bảo trì 2% giá trị căn hộ",
  FAM_NO_UNILATERAL_CHANGE: "Cấm đơn phương thay đổi điều kiện hợp đồng",
  FAM_NO_UNILATERAL_DEFAULT: "Cấm đơn phương ấn định người tiêu dùng vi phạm",
  FAM_PARTY_COMMITMENTS: "Cam kết của các bên tham gia hợp đồng",
  FAM_PARTY_IDENTITY__KDBDS: "Thông tin nhận diện các bên giao kết (KDBĐS)",
  FAM_PARTY_IDENTITY__NHAO: "Thông tin nhận diện các bên giao kết (Luật Nhà ở)",
  FAM_PAYMENT_METHOD_DEADLINE__KDBDS: "Phương thức và thời hạn thanh toán (KDBĐS)",
  FAM_PAYMENT_METHOD_DEADLINE__NHAO: "Phương thức và thời hạn thanh toán (Luật Nhà ở)",
  FAM_PENALTY: "Thỏa thuận phạt vi phạm trong hợp đồng",
  FAM_PRE_CERT_CAP: "Không thu quá 95% giá trị hợp đồng trước khi cấp Sổ hồng",
  FAM_PRE_HANDOVER_CAP: "Không thu quá 70% giá trị hợp đồng trước khi bàn giao nhà",
  FAM_PRICE__KDBDS: "Giá mua bán bất động sản (KDBĐS)",
  FAM_PRICE__NHAO: "Giá giao dịch nhà ở (Luật Nhà ở)",
  FAM_PROGRESS_PAYMENT: "Thanh toán các đợt tiếp theo phù hợp tiến độ xây dựng",
  FAM_PROPERTY_INFO__KDBDS: "Thông tin chi tiết về bất động sản mua bán",
  FAM_RIGHTS_OBLIGATIONS__KDBDS: "Quyền và nghĩa vụ các bên (KDBĐS)",
  FAM_RIGHTS_OBLIGATIONS__NHAO: "Quyền và nghĩa vụ các bên (Luật Nhà ở)",
  FAM_SIGNATURE: "Chữ ký và thể thức văn bản hợp đồng",
  FAM_SIGNING_DATE: "Ngày, tháng, năm giao kết hợp đồng",
  FAM_TEMPLATE_COPY: "Lưu trữ và giao bản sao hợp đồng mẫu cho người tiêu dùng",
  FAM_TEMPLATE_REGISTRATION: "Đăng ký hợp đồng theo mẫu với cơ quan quản lý",
  FAM_TEMPLATE_REVIEW_TIME: "Thời gian hợp lý cho người tiêu dùng nghiên cứu hợp đồng",
  FAM_TERMINATION__KDBDS: "Chấm dứt, hủy bỏ hợp đồng và biện pháp xử lý",
  FAM_TT16: "Hình thức của thỏa thuận trọng tài",
  FAM_TT18: "Hiệu lực của thỏa thuận trọng tài",
  FAM_TT19: "Tính độc lập của điều khoản trọng tài",
  FAM_TT2: "Phạm vi thẩm quyền giải quyết tranh chấp của trọng tài",
  FAM_TT5: "Sự tồn tại của thỏa thuận trọng tài",
  FAM_WARRANTY: "Nội dung bảo hành nhà ở",
  FAM_WARRANTY_MIN_60: "Thời hạn bảo hành nhà chung cư tối thiểu 60 tháng",
  FAM_WARRANTY_RESPONSIBILITY: "Trách nhiệm bảo hành của chủ đầu tư/bên bán",
  FAM_WARRANTY_SCOPE: "Phạm vi và danh mục bảo hành nhà ở",
  FAM_WRITTEN_CONTRACT: "Hình thức văn bản hợp đồng kinh doanh BĐS",
  FAM_WRITTEN_HOUSING_CONTRACT: "Hình thức văn bản hợp đồng về nhà ở",
};

export const REQUIREMENT_VERSION_LABELS: Record<string, string> = {
  PV_HYC040: "Luật Nhà ở 2014 (Điều 163)",
  PV_HYC027: "Luật Kinh doanh BĐS 2014 (Điều 18)",
  PV_HYC053: "Luật Nhà ở 2014 (Điều 85 - Bảo hành)",
  PV_APT_MAINTENANCE_ACCOUNT_2015: "Nghị định 99/2015/NĐ-CP (Tài khoản bảo trì)",
  PV_APT_MAINTENANCE_ACCOUNT_2024: "Nghị định 95/2024/NĐ-CP (Tài khoản bảo trì)",
  PV_APT_COMMON_PRIVATE_2014: "Luật Nhà ở 2014 (Sở hữu chung - riêng)",
  PV_APT_COMMON_PRIVATE_2023: "Luật Nhà ở 2023 (Sở hữu chung - riêng)",
  PV_APT_PARKING_2014: "Luật Nhà ở 2014 (Chỗ để xe)",
  PV_APT_PARKING_2023: "Luật Nhà ở 2023 (Chỗ để xe)",
};

export function formatVersionId(versionId: string | null | undefined): string {
  if (!versionId) return "";
  return REQUIREMENT_VERSION_LABELS[versionId] ?? versionId;
}

/** Formats technical requirement ID into natural Vietnamese */
export function formatRequirementId(rawId: string | null | undefined): string {
  if (!rawId) return "Yêu cầu tuân thủ";
  const famMatch = rawId.match(/(FAM_[A-Za-z0-9_]+)/);
  const famKey = famMatch && famMatch[1] ? famMatch[1] : rawId;
  if (famKey && REQUIREMENT_FAMILY_LABELS[famKey]) {
    return REQUIREMENT_FAMILY_LABELS[famKey];
  }
  if (rawId && REQUIREMENT_FAMILY_LABELS[rawId]) {
    return REQUIREMENT_FAMILY_LABELS[rawId];
  }
  const catalog = requirementsCatalog as Record<string, string>;
  if (catalog[famKey]) {
    return catalog[famKey];
  }
  if (catalog[rawId]) {
    return catalog[rawId];
  }
  let cleaned = rawId
    .replace(/^CA_UP_[A-F0-9]+_/, "")
    .replace(/^FAM_/, "")
    .replace(/__/g, " - ")
    .replace(/_/g, " ");
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1).toLowerCase();
}

/** Formats technical criterion ID into natural Vietnamese fallback */
export function formatCriterionId(id: string | null | undefined): string {
  if (!id) return "Tiêu chí thẩm định";
  const numMatch = id.match(/_0*([1-9]\d*)$/);
  const famMatch = id.match(/(?:TC_PV_|TC_)([A-Za-z0-9]+)/);
  if (numMatch && famMatch) {
    return `Tiêu chí ${numMatch[1]} (${famMatch[1]})`;
  }
  return `Tiêu chí: ${id}`;
}

import { cleanExplanationText } from "../../shared/text";

export { cleanExplanationText };

/** Human-readable criterion text from the knowledge snapshot pinned with the result. */
export function criterionText(criterion: CriterionResult): string {
  const snapshot = criterion.tieu_chi_snapshot_json as Record<string, any> | undefined;
  if (snapshot) {
    if (typeof snapshot.noi_dung === "string" && snapshot.noi_dung.trim()) {
      return snapshot.noi_dung.trim();
    }
    if (typeof snapshot.criterion?.noi_dung === "string" && snapshot.criterion.noi_dung.trim()) {
      return snapshot.criterion.noi_dung.trim();
    }
    if (typeof snapshot.tieu_de === "string" && snapshot.tieu_de.trim()) {
      return snapshot.tieu_de.trim();
    }
    if (typeof snapshot.can_cu_cu_the === "string" && snapshot.can_cu_cu_the.trim()) {
      return `Quy định tại ${snapshot.can_cu_cu_the.trim()}`;
    }
  }
  if (criterion.giai_thich) {
    const cleaned = cleanExplanationText(criterion.giai_thich);
    if (cleaned && cleaned.length > 5 && cleaned !== criterion.giai_thich) {
      return cleaned;
    }
  }
  return formatCriterionId(criterion.tieu_chi_id);
}

/** Human-readable requirement text from the knowledge snapshot pinned with the result. */
export function requirementText(requirement: RequirementResult): string {
  const snapshot = requirement.requirement_snapshot_json as Record<string, any> | undefined;
  if (snapshot) {
    if (typeof snapshot.requirement_version?.noi_dung === "string" && snapshot.requirement_version.noi_dung.trim()) {
      return snapshot.requirement_version.noi_dung.trim();
    }
    if (typeof snapshot.version?.noi_dung === "string" && snapshot.version.noi_dung.trim()) {
      return snapshot.version.noi_dung.trim();
    }
    if (typeof snapshot.requirement?.noi_dung === "string" && snapshot.requirement.noi_dung.trim()) {
      return snapshot.requirement.noi_dung.trim();
    }
    if (typeof snapshot.noi_dung === "string" && snapshot.noi_dung.trim()) {
      return snapshot.noi_dung.trim();
    }
    if (typeof snapshot.ten_yeu_cau === "string" && snapshot.ten_yeu_cau.trim()) {
      return snapshot.ten_yeu_cau.trim();
    }
  }
  return formatRequirementId(requirement.yeu_cau_ca_id);
}

export function riskTitle(
  risk: RiskResult,
  index?: { criterionById?: Map<string, CriterionResult> },
): string {
  const snapshot = risk.risk_snapshot as { ten_rui_ro?: string; mo_ta?: string } | undefined;
  if (snapshot?.ten_rui_ro) return snapshot.ten_rui_ro;
  if (snapshot?.mo_ta) return snapshot.mo_ta;
  if (risk.rui_ro_id === "RR_CITATION_UNKNOWN") {
    return "Viện dẫn pháp lý chưa xác định rõ phiên bản hiệu lực";
  }
  if (index?.criterionById && risk.source.ket_qua_tieu_chi_id) {
    const criterion = index.criterionById.get(risk.source.ket_qua_tieu_chi_id);
    if (criterion) {
      const snap = criterion.tieu_chi_snapshot_json as Record<string, any> | undefined;
      const text = snap?.noi_dung ?? criterionText(criterion);
      if (text && text.length > 5 && !text.startsWith("TC_")) {
        return risk.risk_type === "COMPLIANCE"
          ? `Rủi ro không tuân thủ: ${text}`
          : `Cần xác minh: ${text}`;
      }
    }
  }
  if (risk.rui_ro_id.includes("VIOLATED")) {
    return "Phát hiện có dấu hiệu không tuân thủ quy định pháp luật";
  }
  if (risk.rui_ro_id.includes("UNKNOWN")) {
    return "Cần xác minh và làm rõ điều khoản hợp đồng";
  }
  return risk.rui_ro_id;
}
