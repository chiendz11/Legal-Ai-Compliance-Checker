/**
 * Vietnamese topic names for the knowledge catalogue's obligation groups (yeu_cau_phap_ly.
 * nhom_nghia_vu), in the order a reader goes through a contract. Unknown codes fall into
 * "Nhóm khác" with the code kept visible.
 */
const TOPICS: [code: string, title: string][] = [
  ["I_CHU_THE_DOI_TUONG", "Các bên và đối tượng hợp đồng"],
  ["A_HINH_THUC_NOI_DUNG", "Hình thức và nội dung hợp đồng"],
  ["CAN_HO", "Quy định riêng cho căn hộ chung cư"],
  ["G_DIEU_KIEN_KINH_DOANH", "Điều kiện kinh doanh của bên bán"],
  ["J_GIA_THANH_TOAN_BAO_TRI", "Giá, thanh toán và kinh phí bảo trì"],
  ["G_THANH_TOAN", "Thanh toán"],
  ["N_THUE_BAN_GIAO", "Thuế, phí và bàn giao"],
  ["K_CHAT_LUONG_HA_TANG", "Chất lượng công trình và hạ tầng"],
  ["O_BAO_HANH", "Bảo hành"],
  ["H_NGHIA_VU_BEN_BAN", "Nghĩa vụ của bên bán"],
  ["L_QUYEN_NGHIA_VU_BEN_BAN", "Quyền và nghĩa vụ của bên bán"],
  ["M_QUYEN_NGHIA_VU_BEN_MUA", "Quyền và nghĩa vụ của bên mua"],
  ["P_CHUYEN_NHUONG_SO_HUU_VAN_HANH", "Chuyển nhượng, sở hữu và vận hành nhà chung cư"],
  ["Q_VI_PHAM_CAM_KET", "Vi phạm và cam kết"],
  ["R_BAT_KHA_KHANG_CHAM_DUT_HIEU_LUC", "Bất khả kháng, chấm dứt và hiệu lực"],
  ["C_THUC_HIEN_HOP_DONG", "Thực hiện hợp đồng"],
  ["B_DIEU_KHOAN_CAM", "Điều khoản bị cấm"],
  ["V_NHAT_QUAN_NOI_BO", "Tính nhất quán trong hợp đồng"],
  ["T_CHI_TIET_KIEM_TRA_MAU_IA", "Kiểm tra chi tiết theo hợp đồng mẫu"],
  ["F_SU_DUNG_MAU", "Sử dụng hợp đồng theo mẫu"],
  ["E_DANG_KY_CONG_KHAI", "Đăng ký và công khai hợp đồng mẫu"],
  ["D_TRINH_BAY", "Cách trình bày hợp đồng"],
  ["S_CONG_KHAI_THONG_TIN_DU_AN", "Công khai thông tin dự án"],
  ["U_BAO_VE_THONG_TIN_NGUOI_TIEU_DUNG", "Bảo vệ thông tin người tiêu dùng"],
  ["VB_DS_2015", "Bộ luật Dân sự 2015"],
  ["VB_DT_2023", "Luật Giao dịch điện tử 2023"],
  ["VB_TT_2010", "Luật Trọng tài thương mại 2010"],
  ["HIST_NHAO_2014", "Luật Nhà ở 2014 (quy định cũ)"],
  ["HIST_KDBDS_2014", "Luật Kinh doanh bất động sản 2014 (quy định cũ)"],
  ["HIST_KDBDS_2022", "Nghị định 02/2022 về kinh doanh bất động sản (quy định cũ)"],
  ["HIST_CONSUMER_2010", "Luật Bảo vệ quyền lợi người tiêu dùng 2010 (quy định cũ)"],
];

const ORDER = new Map(TOPICS.map(([code], i) => [code, i]));
const TITLES = new Map(TOPICS);

export const OTHER_TOPIC = "__OTHER__";

export function topicTitle(code: string | null | undefined): string {
  if (!code || code === OTHER_TOPIC) return "Nhóm khác";
  return TITLES.get(code) ?? `Nhóm khác (${code})`;
}

export function topicOrder(code: string): number {
  return ORDER.get(code) ?? TOPICS.length;
}
