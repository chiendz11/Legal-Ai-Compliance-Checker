/** Vietnamese names of contract-profile fields, shared by the profile tab and the reasons. */
export const FIELD_LABELS: Record<string, string> = {
  loai_hop_dong_id: "Loại hợp đồng",
  doi_tuong: "Đối tượng mua bán",
  linh_vuc: "Lĩnh vực",
  he_phap_luat: "Luật điều chỉnh",
  muc_dich_giao_dich: "Mục đích giao dịch",
  ngay_giao_ket: "Ngày ký hợp đồng",
  ngay_giao_ket_raw: "Ngày ký (nguyên văn)",
  do_chinh_xac_ngay: "Độ chính xác ngày",
  trang_thai_ngay: "Trạng thái ngày",
  loai_moc_ap_dung: "Loại mốc áp dụng",
  ngay_hieu_luc_hop_dong: "Ngày hợp đồng có hiệu lực",
  ngay_ban_giao_du_kien: "Ngày bàn giao dự kiến",
  quan_he_chu_the: "Quan hệ giữa các bên",
  ben_ban_co_von_nuoc_ngoai: "Bên bán có vốn nước ngoài",
  ben_ban_la_chu_dau_tu: "Bên bán là chủ đầu tư",
  ben_ban_la_ca_nhan: "Bên bán là cá nhân",
  ben_mua_la_ca_nhan: "Bên mua là cá nhân",
  gia_tri_hop_dong: "Giá bán",
  don_vi_tien: "Đơn vị tiền",
  tinh_trang_tai_san: "Tình trạng tài sản",
  la_nha_o_xa_hoi: "Là nhà ở xã hội",
  la_hop_dong_theo_mau: "Dùng hợp đồng mẫu",
  la_nha_xay_moi: "Là nhà xây mới",
  che_do_giao_dich: "Hình thức giao dịch",
  muc_dich_su_dung_can_ho: "Mục đích sử dụng căn hộ",
  dien_tich: "Diện tích sử dụng căn hộ (m²)",
  gross_area_m2: "Diện tích sàn xây dựng căn hộ (m²)",
  land_area_m2: "Diện tích thửa đất (m²)",
  document_stage: "Trạng thái tài liệu",
  warranty_subject: "Đối tượng bảo hành",
  warranty_months: "Thời hạn bảo hành (tháng)",
  // Conditions the legal catalogue checks but the profile does not (yet) extract.
  loai_chu_the: "Tư cách các bên",
  la_chu_the_kinh_doanh: "Bên bán là chủ thể kinh doanh bất động sản",
  la_giao_dich_dien_tu: "Giao dịch điện tử",
  can_danh_gia_trong_tai: "Điều khoản trọng tài",
};

export function fieldLabel(name: string): string {
  return FIELD_LABELS[name] ?? name;
}
