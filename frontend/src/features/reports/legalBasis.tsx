import { createContext, useContext } from "react";

import type { LegalBasisItem } from "../../shared/api/client";

/** Legal-basis display records by ID; empty until loaded (chips then fall back to raw IDs). */
export const LegalBasisContext = createContext<Map<string, LegalBasisItem>>(new Map());

export const FALLBACK_LEGAL_DOCS: Record<string, { title: string; number?: string }> = {
  VBPL008: { title: "Luật Bảo vệ quyền lợi người tiêu dùng 2010", number: "59/2010/QH12" },
  VBPL001: { title: "Luật Bảo vệ quyền lợi người tiêu dùng 2023", number: "19/2023/QH15" },
  VBPL010: { title: "Luật Kinh doanh bất động sản 2014", number: "66/2014/QH13" },
  VBPL005: { title: "Luật Kinh doanh bất động sản 2023", number: "29/2023/QH15" },
  VBPL011: { title: "Luật Nhà ở 2014", number: "65/2014/QH13" },
  VBPL007: { title: "Luật Nhà ở 2023", number: "27/2023/QH15" },
  VB_DS_2015: { title: "Bộ luật Dân sự 2015", number: "91/2015/QH13" },
  VB_TT_2010: { title: "Luật Trọng tài thương mại 2010", number: "54/2010/QH12" },
  VB_43_2024: { title: "Luật sửa đổi hiệu lực các luật BĐS", number: "43/2024/QH15" },
  VB_DT_2023: { title: "Luật Giao dịch điện tử 2023", number: "20/2023/QH15" },
  VB_ND76_2015: { title: "Nghị định quy định chi tiết Luật KDBĐS 2014", number: "76/2015/NĐ-CP" },
  VBPL013: { title: "Nghị định quy định chi tiết Luật KDBĐS (Mẫu 01)", number: "02/2022/NĐ-CP" },
  VBPL004: { title: "Nghị định quy định chi tiết Luật KDBĐS 2023", number: "96/2024/NĐ-CP" },
  VBPL006: { title: "Mẫu Ia Mua bán căn hộ chung cư (Nghị định 96/2024)", number: "Phụ lục I Mẫu Ia" },
  VB_ND99_2015: { title: "Nghị định quy định chi tiết Luật Nhà ở 2014", number: "99/2015/NĐ-CP" },
  VB_ND95_2024: { title: "Nghị định quy định chi tiết Luật Nhà ở 2023", number: "95/2024/NĐ-CP" },
  VB_ND100_2024: { title: "Nghị định phát triển và quản lý nhà ở xã hội", number: "100/2024/NĐ-CP" },
  VB_ND261_2025: { title: "Nghị định sửa đổi về nhà ở xã hội", number: "261/2025/NĐ-CP" },
  VB_ND136_2026: { title: "Nghị định sửa đổi về điều kiện thu nhập NOXH", number: "136/2026/NĐ-CP" },
  VB_ND54_2026: { title: "Nghị định sửa đổi các NĐ lĩnh vực nhà ở, BĐS", number: "54/2026/NĐ-CP" },
  VB_ND146_2025: { title: "Nghị định phân quyền, phân cấp thương mại", number: "146/2025/NĐ-CP" },
  VB_ND99_2011: { title: "Nghị định quy định chi tiết Luật BVNTD 2010", number: "99/2011/NĐ-CP" },
  VBPL002: { title: "Nghị định quy định chi tiết Luật BVNTD 2023", number: "55/2024/NĐ-CP" },
  VBPL012: { title: "Nghị định sửa đổi Nghị định 99/2015/NĐ-CP", number: "30/2021/NĐ-CP" },
  VB_QD02_2012: { title: "Quyết định danh mục hàng hóa thiết yếu đăng ký mẫu", number: "02/2012/QĐ-TTg" },
  VB_QD35_2015: { title: "Quyết định sửa đổi danh mục hàng hóa thiết yếu", number: "35/2015/QĐ-TTg" },
  VBPL003: { title: "Quyết định danh mục hàng hóa thiết yếu đăng ký mẫu", number: "07/2024/QĐ-TTg" },
  VB_TT02_2016: { title: "Quy chế quản lý, sử dụng nhà chung cư", number: "02/2016/TT-BXD" },
  VB_TT28_2016: { title: "Thông tư sửa đổi Quy chế quản lý chung cư", number: "28/2016/TT-BXD" },
  VB_TT06_2019: { title: "Thông tư sửa đổi các thông tư quản lý chung cư", number: "06/2019/TT-BXD" },
  VB_TT10_2015: { title: "Thông tư đào tạo quản lý vận hành chung cư", number: "10/2015/TT-BXD" },
  VB_TT11_2015: { title: "Thông tư chứng chỉ hành nghề môi giới BĐS", number: "11/2015/TT-BXD" },
  VB_TT19_2016: { title: "Thông tư hướng dẫn Luật Nhà ở và NĐ 99/2015", number: "19/2016/TT-BXD" },
  VB_TT42_2025: { title: "Danh mục sản phẩm thiết yếu phải đăng ký HĐ mẫu", number: "42/2025/TT-BCT" },
  VB_NHAO_HN2025: { title: "Văn bản hợp nhất Luật Nhà ở", number: "132/VBHN-VPQH" },
  VB_ND96_HN2026: { title: "Văn bản hợp nhất Nghị định 96/2024/NĐ-CP", number: "VBHN NĐ 96/2024" },
};

export function formatDocId(id: string): string {
  if (!id) return "";
  const fallback = FALLBACK_LEGAL_DOCS[id];
  if (fallback) {
    return fallback.number ? `${fallback.title} (${fallback.number})` : fallback.title;
  }
  // Format ART_VB_DS_2015_418 -> Điều 418 Bộ luật Dân sự 2015
  const artDsMatch = id.match(/ART_VB_DS_2015_(\d+)/);
  if (artDsMatch && artDsMatch[1]) {
    return `Điều ${artDsMatch[1]} Bộ luật Dân sự 2015`;
  }
  // Format ART_VBPL011_85 -> Điều 85 Luật Nhà ở 2014
  const artVbplMatch = id.match(/ART_(VBPL\d+)_(\d+)/);
  if (artVbplMatch && artVbplMatch[1] && artVbplMatch[2]) {
    const docId = artVbplMatch[1];
    const artNum = artVbplMatch[2];
    const docName = FALLBACK_LEGAL_DOCS[docId]?.title ?? docId;
    return `Điều ${artNum} ${docName}`;
  }
  // Format article IDs like DK_NHAO2014_D85 -> Điều 85 Luật Nhà ở 2014
  const articleMatch = id.match(/DK_([A-Za-z0-9]+)_D(\d+)/);
  if (articleMatch && articleMatch[1] && articleMatch[2]) {
    const docCode = articleMatch[1];
    const articleNum = articleMatch[2];
    const docName = docCode.includes("NHAO")
      ? "Luật Nhà ở"
      : docCode.includes("KDBDS")
      ? "Luật Kinh doanh BĐS"
      : docCode.includes("DS")
      ? "Bộ luật Dân sự"
      : docCode;
    return `Điều ${articleNum} ${docName}`;
  }
  // Format standardized DKPL clause ID
  if (id.startsWith("DKPL")) {
    return `Điều khoản chuẩn hóa #${id.slice(4)}`;
  }
  // Format requirement version code PV_...
  if (id.startsWith("PV_")) {
    return `Quy định ${id}`;
  }
  return id;
}

function chipText(item: LegalBasisItem): string {
  const number = item.document?.so_hieu;
  switch (item.kind) {
    case "DOCUMENT":
      return [item.number, item.title].filter(Boolean).join(" – ");
    case "ARTICLE":
      return [item.title, number].filter(Boolean).join(", ");
    case "REQUIREMENT_VERSION":
      return `Yêu cầu ${item.id}${number ? ` (${number})` : ""}`;
    default:
      return item.id;
  }
}

function tooltip(item: LegalBasisItem): string {
  return [
    item.id,
    item.kind === "REQUIREMENT_VERSION" || item.kind === "ARTICLE" ? item.title : null,
    item.document?.ten_van_ban,
    item.effective_from && `Hiệu lực từ ${item.effective_from}${item.effective_to ? ` đến ${item.effective_to}` : ""}`,
    item.excerpt,
    item.verification && `Xác minh: ${item.verification}`,
  ]
    .filter(Boolean)
    .join("\n");
}

/** Legal sources still awaiting human review are marked; flags are never upgraded here. */
const unverified = (item: LegalBasisItem) =>
  !!item.verification && /CHUA|PENDING|UNVERIFIED/.test(item.verification);

export function LegalBasis({ ids, empty = "—" }: { ids: string[] | undefined; empty?: string }) {
  const known = useContext(LegalBasisContext);
  if (!ids?.length) return <span className="muted">{empty}</span>;
  return (
    <span className="ids">
      {ids.map((id) => {
        const item = known.get(id);
        if (!item || item.kind === "UNKNOWN") {
          const friendly = formatDocId(id);
          return (
            <span key={id} className="basis" title={id}>
              {friendly}
            </span>
          );
        }
        const text = chipText(item);
        return (
          <span key={id} className="basis" title={tooltip(item)}>
            {item.url ? (
              <a href={item.url} target="_blank" rel="noreferrer">
                {text}
              </a>
            ) : (
              text
            )}
            {unverified(item) && <span className="tag">chưa duyệt</span>}
          </span>
        );
      })}
    </span>
  );
}
