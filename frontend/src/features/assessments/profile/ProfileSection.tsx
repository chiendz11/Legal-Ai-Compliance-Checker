import type { ContractProfile } from "../../../shared/api/client";
import {
  Disclosure,
  Empty,
  Fields,
  Quote,
  Section,
  Table,
  Value,
} from "../../../shared/components/ui";
import { useReportIndex } from "../../reports/reportIndex";

const PROFILE_LABELS: Record<string, string> = {
  loai_hop_dong_id: "Loại hợp đồng",
  doi_tuong: "Đối tượng",
  linh_vuc: "Lĩnh vực",
  he_phap_luat: "Hệ pháp luật",
  muc_dich_giao_dich: "Mục đích giao dịch",
  ngay_giao_ket: "Ngày giao kết",
  ngay_giao_ket_raw: "Ngày giao kết (gốc)",
  do_chinh_xac_ngay: "Độ chính xác ngày",
  trang_thai_ngay: "Trạng thái ngày",
  loai_moc_ap_dung: "Loại mốc áp dụng",
  ngay_hieu_luc_hop_dong: "Ngày hiệu lực",
  ngay_ban_giao_du_kien: "Ngày bàn giao dự kiến",
  quan_he_chu_the: "Quan hệ chủ thể",
  ben_ban_co_von_nuoc_ngoai: "Bên bán có vốn nước ngoài",
  ben_ban_la_chu_dau_tu: "Bên bán là chủ đầu tư",
  ben_ban_la_ca_nhan: "Bên bán là cá nhân",
  ben_mua_la_ca_nhan: "Bên mua là cá nhân",
  gia_tri_hop_dong: "Giá trị hợp đồng",
  don_vi_tien: "Đơn vị tiền",
  tinh_trang_tai_san: "Tình trạng tài sản",
  la_nha_o_xa_hoi: "Nhà ở xã hội",
  la_hop_dong_theo_mau: "Hợp đồng theo mẫu",
  la_nha_xay_moi: "Nhà xây mới",
  che_do_giao_dich: "Chế độ giao dịch",
  muc_dich_su_dung_can_ho: "Mục đích sử dụng căn hộ",
};

export function ProfileSection({ profile }: { profile: ContractProfile }) {
  const index = useReportIndex();
  const fields = Object.entries(profile.profile);
  const unknownCount = fields.filter(([, v]) => v === null).length;
  return (
    <Section
      title="Hồ sơ hợp đồng"
      description={`C02 dùng để xác định phạm vi và mốc thời gian. ${unknownCount} trường chưa xác định được giữ nguyên là chưa có.`}
    >
      <Fields rows={fields.map(([k, v]) => [PROFILE_LABELS[k] ?? k, <Value value={v} />])} />

      <h3 className="subhead">Chủ thể</h3>
      {profile.subjects?.length ? (
        <Table>
          <thead>
            <tr>
              <th>Vai trò</th>
              <th>Tên</th>
              <th>Loại</th>
              <th>Thương nhân</th>
              <th>Chủ thể kinh doanh</th>
              <th>Đoạn bằng chứng</th>
            </tr>
          </thead>
          <tbody>
            {profile.subjects.map((s) => (
              <tr key={s.chu_the_id}>
                <td>{s.vai_tro}</td>
                <td>
                  <Value value={s.ten_chu_the} />
                </td>
                <td>
                  <Value value={s.loai_chu_the} />
                </td>
                <td>
                  <Value value={s.la_thuong_nhan} />
                </td>
                <td>
                  <Value value={s.la_chu_the_kinh_doanh} />
                </td>
                <td>
                  <code>{s.doan_bang_chung_id ?? "—"}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <Empty>Chưa trích xuất chủ thể.</Empty>
      )}

      <h3 className="subhead">Mốc thời gian</h3>
      {profile.time_markers?.length ? (
        <Table>
          <thead>
            <tr>
              <th>Loại mốc</th>
              <th>Ngày</th>
              <th>Giá trị gốc</th>
              <th>Độ chính xác</th>
              <th>Dùng để phân giải</th>
              <th>Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {profile.time_markers.map((m) => (
              <tr key={m.moc_id}>
                <td>{m.loai_moc}</td>
                <td>
                  <Value value={m.ngay} />
                </td>
                <td>
                  <Value value={m.gia_tri_raw} />
                </td>
                <td>
                  <Value value={m.do_chinh_xac} />
                </td>
                <td>
                  <Value value={m.duoc_dung_phan_giai} />
                </td>
                <td className="small">{m.trang_thai}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <Empty>Chưa có mốc thời gian.</Empty>
      )}

      <h3 className="subhead">Dữ kiện trích xuất ({profile.facts?.length ?? 0})</h3>
      <div className="stack">
        {profile.facts?.map((f) => (
          <Disclosure
            key={f.trich_xuat_id}
            summary={
              <>
                <code>{f.ten_truong}</code> <Value value={f.gia_tri_chuan_json} />
                {!f.human_verified && <span className="tag">chưa xác minh</span>}
              </>
            }
          >
            <p className="small muted">
              {f.phuong_phap} · {f.trang_thai}
            </p>
            {(f.evidence_ids ?? []).map((id) => {
              const e = index.profileEvidenceById.get(id);
              return e ? (
                <Quote
                  key={id}
                  text={e.trich_dan}
                  chunkId={e.doan_id}
                  start={e.ky_tu_bat_dau}
                  end={e.ky_tu_ket_thuc}
                />
              ) : (
                <p key={id} className="uncertain">
                  Thiếu bằng chứng <code>{id}</code> trong report.
                </p>
              );
            })}
          </Disclosure>
        ))}
      </div>
    </Section>
  );
}
