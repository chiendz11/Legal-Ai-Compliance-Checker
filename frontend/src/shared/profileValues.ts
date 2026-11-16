/**
 * Plain Vietnamese for contract-profile values. The profile stores catalogue codes
 * (MB_CAN_HO_CHUNG_CU, HINH_THANH_TRONG_TUONG_LAI, DE_O…); readers need words, dates as
 * dd/mm/yyyy and amounts with thousand separators. Unknown codes are humanised, never hidden.
 */
const VALUE_LABELS: Record<string, Record<string, string>> = {
  loai_hop_dong_id: {
    MB_CAN_HO_CHUNG_CU: "Mua bán căn hộ chung cư",
    MB_BAT_DONG_SAN: "Mua bán bất động sản",
    MB_HOP_DONG_MUA_BAN: "Hợp đồng mua bán",
  },
  doi_tuong: { NHA_O: "Nhà ở" },
  linh_vuc: { NHA_O: "Nhà ở" },
  he_phap_luat: { VIET_NAM: "Pháp luật Việt Nam" },
  muc_dich_giao_dich: {
    TIEU_DUNG_KHONG_THUONG_MAI: "Mua để sử dụng (tiêu dùng, không kinh doanh)",
  },
  quan_he_chu_the: {
    DOANH_NGHIEP_VA_CA_NHAN: "Doanh nghiệp bán cho cá nhân",
  },
  tinh_trang_tai_san: {
    HINH_THANH_TRONG_TUONG_LAI: "Nhà hình thành trong tương lai (chưa xây xong)",
    CO_SAN: "Nhà có sẵn",
    DA_HOAN_THANH: "Nhà đã hoàn thành",
  },
  che_do_giao_dich: {
    KINH_DOANH_BDS: "Kinh doanh bất động sản (chủ đầu tư bán)",
    LUAT_NHA_O: "Mua bán nhà ở thông thường (Luật Nhà ở)",
    BAN_LAI_CA_NHAN: "Cá nhân bán lại",
    NOXH: "Nhà ở xã hội",
  },
  muc_dich_su_dung_can_ho: { DE_O: "Để ở" },
  loai_moc_ap_dung: {
    NGAY_GIAO_KET: "Ngày ký hợp đồng",
    NGAY_HIEU_LUC: "Ngày hợp đồng có hiệu lực",
    NGAY_SU_KIEN: "Ngày phát sinh sự kiện",
    TEMPLATE_USE: "Ngày sử dụng hợp đồng mẫu",
  },
  do_chinh_xac_ngay: { DAY: "Theo ngày", MONTH: "Theo tháng", YEAR: "Chỉ biết năm" },
  trang_thai_ngay: {
    EXTRACTED: "Đọc từ hợp đồng",
    SYNTHETIC_SOURCE_EXTRACTED: "Đọc từ dữ liệu mẫu",
  },
};

const DATE_FIELDS = new Set(["ngay_giao_ket", "ngay_hieu_luc_hop_dong", "ngay_ban_giao_du_kien"]);

const ROLE_LABELS: Record<string, string> = { BEN_BAN: "Bên bán", BEN_MUA: "Bên mua" };
const SUBJECT_KIND: Record<string, string> = {
  DOANH_NGHIEP: "Doanh nghiệp",
  CA_NHAN: "Cá nhân",
  TO_CHUC: "Tổ chức",
};

function humanise(code: string): string {
  const text = code.replace(/_/g, " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function isoDate(value: string): string | null {
  const m = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : null;
}

const money = new Intl.NumberFormat("vi-VN");

/** Display text for one profile field; null/UNKNOWN become null so callers list them as missing. */
export function profileValue(
  field: string,
  value: unknown,
  profile: Record<string, unknown> = {},
): string | null {
  if (value === null || value === undefined || value === "UNKNOWN") return null;
  if (typeof value === "boolean") return value ? "Có" : "Không";
  if (field === "gia_tri_hop_dong") {
    const amount = Number(value);
    const unit = profile.don_vi_tien === "VND" || !profile.don_vi_tien ? "đồng" : String(profile.don_vi_tien);
    return Number.isFinite(amount) ? `${money.format(amount)} ${unit}` : String(value);
  }
  if (typeof value === "string") {
    if (DATE_FIELDS.has(field)) return isoDate(value) ?? value;
    const labels = VALUE_LABELS[field];
    if (labels) return labels[value] ?? humanise(value);
    return isoDate(value) ?? value;
  }
  if (typeof value === "number") return money.format(value);
  return JSON.stringify(value);
}

export function roleLabel(code: string | null | undefined): string {
  return code ? (ROLE_LABELS[code] ?? humanise(code)) : "Không rõ vai trò";
}

export function subjectKind(code: string | null | undefined): string | null {
  return code ? (SUBJECT_KIND[code] ?? humanise(code)) : null;
}

/** Fields grouped the way a reader looks at a contract. Technical fields are listed apart. */
export const PROFILE_GROUPS: { title: string; fields: string[] }[] = [
  { title: "Hợp đồng", fields: ["loai_hop_dong_id", "doi_tuong", "linh_vuc", "he_phap_luat", "la_hop_dong_theo_mau"] },
  { title: "Thời gian", fields: ["ngay_giao_ket", "ngay_hieu_luc_hop_dong", "ngay_ban_giao_du_kien"] },
  { title: "Giá trị", fields: ["gia_tri_hop_dong"] },
  {
    title: "Các bên và giao dịch",
    fields: [
      "quan_he_chu_the",
      "ben_ban_la_chu_dau_tu",
      "ben_ban_la_ca_nhan",
      "ben_ban_co_von_nuoc_ngoai",
      "ben_mua_la_ca_nhan",
      "che_do_giao_dich",
      "muc_dich_giao_dich",
    ],
  },
  {
    title: "Căn hộ",
    fields: ["tinh_trang_tai_san", "la_nha_xay_moi", "la_nha_o_xa_hoi", "muc_dich_su_dung_can_ho"],
  },
];

/** Shown only under technical detail: they describe how a value was read, not the contract. */
export const TECHNICAL_FIELDS = ["ngay_giao_ket_raw", "do_chinh_xac_ngay", "trang_thai_ngay", "loai_moc_ap_dung", "don_vi_tien"];
