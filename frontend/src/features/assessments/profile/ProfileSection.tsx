import type { ContractProfile, ProfileEvidence } from "../../../shared/api/client";
import { Disclosure, Empty, Quote, Section, Table, Value } from "../../../shared/components/ui";
import { FIELD_LABELS } from "../../../shared/fieldLabels";
import { label } from "../../../shared/labels";
import {
  PROFILE_GROUPS,
  profileValue,
  roleLabel,
  subjectKind,
  TECHNICAL_FIELDS,
} from "../../../shared/profileValues";
import { viDate } from "../../reports/explain";
import { useReportIndex } from "../../reports/reportIndex";
import { useOpenEvidence } from "../evidence/EvidenceViewer";

const fieldName = (key: string) => FIELD_LABELS[key] ?? key;

export function ProfileSection({ profile }: { profile: ContractProfile }) {
  const index = useReportIndex();
  const openEvidence = useOpenEvidence();
  const values = profile.profile as Record<string, unknown>;
  const facts = new Map((profile.facts ?? []).map((f) => [f.ten_truong, f]));
  const evidenceOf = (key: string): ProfileEvidence | undefined => {
    const id = facts.get(`profile.${key}`)?.evidence_ids?.[0];
    return id ? index.profileEvidenceById.get(id) : undefined;
  };
  const open = (e: ProfileEvidence) =>
    openEvidence?.({
      doanId: e.doan_id,
      start: e.ky_tu_bat_dau,
      end: e.ky_tu_ket_thuc,
      quote: e.trich_dan,
    });
  const grouped = new Set(PROFILE_GROUPS.flatMap((g) => g.fields));
  const otherFields = Object.keys(values).filter(
    (k) => !grouped.has(k) && !TECHNICAL_FIELDS.includes(k),
  );
  const groups = [...PROFILE_GROUPS, { title: "Khác", fields: otherFields }];
  const missing = groups
    .flatMap((g) => g.fields)
    .filter((k) => k in values && profileValue(k, values[k], values) === null);
  const markers = profile.time_markers ?? [];
  const datedMarkers = markers.filter((m) => m.ngay);
  const undatedMarkers = markers.filter((m) => !m.ngay);

  return (
    <Section
      title="Thông tin hợp đồng"
      description="Những gì hệ thống đọc được từ hợp đồng. Các thông tin này quyết định quy định nào áp dụng và luật tại thời điểm nào được dùng. Thông tin không tìm thấy được để trống, hệ thống không tự đoán. Bấm “Xem trong hợp đồng” để đối chiếu với văn bản gốc."
    >
      <div className="profile-grid">
        {groups.map((group) => {
          const rows = group.fields
            .map((key) => [key, profileValue(key, values[key], values)] as const)
            .filter((row): row is readonly [string, string] => row[1] !== null);
          if (rows.length === 0) return null;
          return (
            <section key={group.title} className="profile-card">
              <h3>{group.title}</h3>
              <dl>
                {rows.map(([key, text]) => {
                  const evidence = evidenceOf(key);
                  return (
                    <div key={key}>
                      <dt>{fieldName(key)}</dt>
                      <dd>
                        {text}
                        {evidence && openEvidence && (
                          <button type="button" className="link small source-link" onClick={() => open(evidence)}>
                            Xem trong hợp đồng
                          </button>
                        )}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            </section>
          );
        })}
      </div>
      {missing.length > 0 && (
        <p className="missing-line">
          <strong>Không tìm thấy trong hợp đồng ({missing.length}):</strong>{" "}
          {missing.map(fieldName).join(", ")}.
        </p>
      )}

      <h3 className="subhead">Các bên</h3>
      {profile.subjects?.length ? (
        <div className="profile-grid">
          {profile.subjects.map((s) => {
            const traits = [
              subjectKind(s.loai_chu_the),
              s.la_thuong_nhan ? "Thương nhân" : null,
              s.la_chu_the_kinh_doanh ? "Kinh doanh bất động sản" : null,
            ].filter(Boolean);
            return (
              <section key={s.chu_the_id} className="profile-card">
                <h3>{roleLabel(s.vai_tro)}</h3>
                <p className="party-name">{s.ten_chu_the ?? "Không rõ tên"}</p>
                {traits.length > 0 && <p className="muted small">{traits.join(" · ")}</p>}
              </section>
            );
          })}
        </div>
      ) : (
        <Empty>Không đọc được thông tin các bên trong hợp đồng.</Empty>
      )}

      <h3 className="subhead">Các mốc thời gian</h3>
      {datedMarkers.length > 0 ? (
        <ul className="marker-list">
          {datedMarkers.map((m) => (
            <li key={m.moc_id}>
              <span>{label("markerType", m.loai_moc).text}</span>
              <strong>{viDate(m.ngay)}</strong>
            </li>
          ))}
        </ul>
      ) : (
        <Empty>Không đọc được mốc thời gian nào trong hợp đồng.</Empty>
      )}
      {undatedMarkers.length > 0 && (
        <p className="missing-line">
          <strong>Không tìm thấy ngày:</strong>{" "}
          {undatedMarkers.map((m) => label("markerType", m.loai_moc).text.toLowerCase()).join(", ")}.
        </p>
      )}

      <Disclosure summary="Chi tiết kỹ thuật: cách hệ thống đọc từng thông tin (dành cho kỹ sư)">
        <h4 className="minihead">Trường kỹ thuật</h4>
        <dl className="fields compact">
          {TECHNICAL_FIELDS.filter((k) => k in values).map((k) => (
            <div key={k}>
              <dt>{fieldName(k)}</dt>
              <dd>{profileValue(k, values[k], values) ?? <span className="null">chưa có</span>}</dd>
            </div>
          ))}
        </dl>
        <h4 className="minihead">Mốc thời gian</h4>
        <Table>
          <thead>
            <tr>
              <th>Loại mốc</th>
              <th>Ngày</th>
              <th>Giá trị gốc</th>
              <th>Độ chính xác</th>
              <th>Dùng để chọn luật</th>
              <th>Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {markers.map((m) => (
              <tr key={m.moc_id}>
                <td title={m.loai_moc}>{label("markerType", m.loai_moc).text}</td>
                <td>{m.ngay ? viDate(m.ngay) : <Value value={null} />}</td>
                <td>
                  <Value value={m.gia_tri_raw} />
                </td>
                <td>{m.do_chinh_xac ? label("precision", m.do_chinh_xac).text : <Value value={null} />}</td>
                <td>
                  <Value value={m.duoc_dung_phan_giai} />
                </td>
                <td className="small" title={m.trang_thai}>
                  {label("markerStatus", m.trang_thai).text}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
        <h4 className="minihead">Dữ kiện trích xuất ({profile.facts?.length ?? 0})</h4>
        <div className="stack">
          {profile.facts?.map((f) => (
            <Disclosure
              key={f.trich_xuat_id}
              summary={
                <>
                  <span title={f.ten_truong}>{fieldName(f.ten_truong)}</span>{" "}
                  <Value value={f.gia_tri_chuan_json} />{" "}
                  {!f.human_verified && <span className="tag">chưa xác minh</span>}
                </>
              }
            >
              <p className="small muted">
                Phương pháp <code>{f.phuong_phap}</code> · trạng thái{" "}
                <span title={f.trang_thai}>{label("markerStatus", f.trang_thai).text}</span>
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
                    onOpen={openEvidence ? () => open(e) : undefined}
                  />
                ) : (
                  <p key={id} className="uncertain">
                    Thiếu bằng chứng <code>{id}</code> trong báo cáo.
                  </p>
                );
              })}
            </Disclosure>
          ))}
        </div>
      </Disclosure>
    </Section>
  );
}
