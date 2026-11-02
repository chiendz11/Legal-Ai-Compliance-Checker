"""Document metadata/chunk persistence. Source byte storage is shared/storage/source.py.

- Đọc C01 theo Q10 (tệp chính do ``hop_dong.tep_nguon_id`` chỉ định, không lấy row đầu).
- Ghi chunks, facts/evidence, chủ thể, mốc, viện dẫn trong MỘT transaction. Các ID đều chứa
  extraction version nên chạy lại cùng version không nhân đôi (ON CONFLICT DO NOTHING) và
  không đụng dữ liệu seed.
- ``ho_so_hop_dong`` chỉ có một dòng/hợp đồng (chưa có cột version, mục 8.4): đã có dòng thì
  mặc định giữ nguyên, chỉ ghi đè khi ``replace_profile=True``.
"""

from dataclasses import dataclass
from datetime import date, datetime

from psycopg.types.json import Jsonb

from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.documents.service import DocumentExtraction
from legal_checker.shared.contracts.assessment import AssessmentCase, SourceDocument
from legal_checker.shared.contracts.common import DeploymentPin

LOAI_DU_LIEU = "DI_PIPELINE_OUTPUT"
TRANG_THAI_PROFILE = "DI_EXTRACTED_REVIEW_PENDING"

Q10_INTAKE = """
SELECT ca.ca_id, ca.hop_dong_id, ca.tenant_id, ca.created_by,
       ca.ngay_danh_gia, ca.moc_ap_dung, ca.loai_moc_ap_dung,
       ca.phien_ban_id, ca.rule_version, ca.legal_knowledge_version,
       t.tep_id, t.object_uri, t.url_nguon, t.mime_type, t.sha256
FROM runtime.ca_danh_gia ca
JOIN runtime.hop_dong h ON h.hop_dong_id = ca.hop_dong_id
JOIN runtime.tep_nguon t ON t.tep_id = h.tep_nguon_id AND t.hop_dong_id = h.hop_dong_id
WHERE ca.ca_id = %(case_id)s
"""

PROFILE_COLUMNS = (
    "loai_hop_dong_id",
    "doi_tuong",
    "linh_vuc",
    "he_phap_luat",
    "muc_dich_giao_dich",
    "ngay_giao_ket",
    "doan_bang_chung_ngay_id",
    "loai_moc_ap_dung",
    "tinh_trang_tai_san",
    "la_nha_o_xa_hoi",
    "la_hop_dong_theo_mau",
    "ben_ban_co_von_nuoc_ngoai",
    "trang_thai_profile",
    "ngay_giao_ket_raw",
    "do_chinh_xac_ngay",
    "trang_thai_ngay",
    "quan_he_chu_the",
    "loai_du_lieu",
    "gia_tri_hop_dong",
    "don_vi_tien",
    "ngay_hieu_luc_hop_dong",
    "ngay_ban_giao_du_kien",
    "che_do_giao_dich",
    "ben_ban_la_chu_dau_tu",
    "la_nha_xay_moi",
    "ben_ban_la_ca_nhan",
    "ben_mua_la_ca_nhan",
    "muc_dich_su_dung_can_ho",
)
# Các cờ lưu dạng TEXT CO/KHONG/UNKNOWN trong DB nhưng là bool | None trong DTO (mục 8.2).
TEXT_FLAG_COLUMNS = {"la_hop_dong_theo_mau", "ben_ban_co_von_nuoc_ngoai"}


@dataclass(frozen=True)
class SaveReport:
    hop_dong_id: str
    version: str
    chunks: int
    facts: int
    evidence: int
    subjects: int
    markers: int
    citations: int
    citation_positions: int
    profile_written: bool
    profile_note: str


def _flag(value: bool | None) -> str:
    return "UNKNOWN" if value is None else ("CO" if value else "KHONG")


def _to_date(value) -> date | None:
    # ngay_danh_gia có thể là TIMESTAMPTZ; connect_postgres đặt TIME ZONE 'UTC'.
    return value.date() if isinstance(value, datetime) else value


def case_from_row(row: dict) -> AssessmentCase:
    """Q10 row → C01. Chỉ lấy cột DTO nhận; cột model/prompt của deployment không đưa vào."""
    return AssessmentCase(
        ca_id=row["ca_id"],
        hop_dong_id=row["hop_dong_id"],
        source=SourceDocument(
            tep_id=row["tep_id"],
            object_uri=row["object_uri"],
            url_nguon=row["url_nguon"],
            mime_type=row["mime_type"],
            sha256=(row["sha256"] or "").strip().lower(),
        ),
        assessment_context={
            "ngay_danh_gia": _to_date(row["ngay_danh_gia"]),
            "moc_ap_dung": _to_date(row["moc_ap_dung"]),
            "loai_moc_ap_dung": row["loai_moc_ap_dung"],
        },
        deployment=DeploymentPin(
            phien_ban_id=row["phien_ban_id"],
            rule_version=row["rule_version"],
            legal_knowledge_version=row["legal_knowledge_version"],
        ),
        tenant_id=row["tenant_id"],
        created_by=row["created_by"],
    )


class DocumentRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def load_case(self, case_id: str) -> AssessmentCase:
        with connect_postgres(self.database_url) as conn:
            row = conn.execute(Q10_INTAKE, {"case_id": case_id}).fetchone()
        if row is None:
            raise LookupError(f"Case {case_id} not found or has no primary source file")
        return case_from_row(row)

    def save(self, extraction: DocumentExtraction, *, replace_profile: bool = False) -> SaveReport:
        hd = extraction.case.hop_dong_id
        version = extraction.version
        profile = extraction.result.contract_profile
        with connect_postgres(self.database_url) as conn, conn.transaction():
            cur = conn.cursor()
            chunk_rows = [
                (
                    c.doan_id,
                    c.hop_dong_id,
                    c.section_path,
                    c.page_start,
                    c.page_end,
                    c.noi_dung,
                    "TEXT_LAYER",
                    c.sha256,
                    c.thu_tu,
                    version,
                    LOAI_DU_LIEU,
                )
                for c in extraction.chunks
            ]
            cur.executemany(
                """INSERT INTO runtime.doan_hop_dong (doan_id, hop_dong_id, section_path,
                   page_start, page_end, noi_dung, chunk_quality, sha256_text, thu_tu,
                   phien_ban_chunk, loai_du_lieu)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                chunk_rows,
            )

            cur.executemany(
                """INSERT INTO runtime.trich_xuat_truong (trich_xuat_id, hop_dong_id, ten_truong,
                   gia_tri_raw, gia_tri_chuan_json, trang_thai, phuong_phap, human_verified,
                   ngay_trich_xuat, ghi_chu, loai_du_lieu)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,now(),%s,%s) ON CONFLICT DO NOTHING""",
                [
                    (
                        f.trich_xuat_id,
                        hd,
                        f.ten_truong,
                        f.gia_tri_raw,
                        None if f.gia_tri_chuan_json is None else Jsonb(f.gia_tri_chuan_json),
                        f.trang_thai,
                        f.phuong_phap,
                        f.human_verified,
                        f"extraction_version={version}",
                        LOAI_DU_LIEU,
                    )
                    for f in profile.facts
                ],
            )
            fact_of_evidence = {e: f.trich_xuat_id for f in profile.facts for e in f.evidence_ids}
            cur.executemany(
                """INSERT INTO runtime.bang_chung_truong (bang_chung_id, trich_xuat_id, doan_id,
                   trich_dan_nguyen_van, ky_tu_bat_dau, ky_tu_ket_thuc, loai_du_lieu)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                [
                    (
                        e.bang_chung_id,
                        fact_of_evidence[e.bang_chung_id],
                        e.doan_id,
                        e.trich_dan,
                        e.ky_tu_bat_dau,
                        e.ky_tu_ket_thuc,
                        LOAI_DU_LIEU,
                    )
                    for e in profile.evidence
                ],
            )
            profile_chunks = sorted({e.doan_id for e in profile.evidence})
            cur.executemany(
                """INSERT INTO runtime.bang_chung_ho_so (lien_ket_id, hop_dong_id, doan_id,
                   loai_du_lieu) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                [
                    (f"{hd}_BCHS_{version}_{i:03d}", hd, doan_id, LOAI_DU_LIEU)
                    for i, doan_id in enumerate(profile_chunks, start=1)
                ],
            )

            cur.executemany(
                """INSERT INTO runtime.chu_the_hop_dong (chu_the_id, hop_dong_id, vai_tro,
                   loai_chu_the, la_thuong_nhan, la_chu_the_kinh_doanh, ten_chu_the,
                   doan_bang_chung_id, trang_thai, ten_raw, human_verified, loai_du_lieu)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                [
                    (
                        s.chu_the_id,
                        hd,
                        s.vai_tro,
                        s.loai_chu_the,
                        _flag(s.la_thuong_nhan),
                        _flag(s.la_chu_the_kinh_doanh),
                        s.ten_chu_the,
                        s.doan_bang_chung_id,
                        "EXTRACTED",
                        s.ten_chu_the,
                        s.human_verified,
                        LOAI_DU_LIEU,
                    )
                    for s in profile.subjects
                ],
            )
            cur.executemany(
                """INSERT INTO runtime.moc_thoi_gian_hop_dong (moc_id, hop_dong_id, loai_moc,
                   gia_tri_raw, ngay, nam, do_chinh_xac, trang_thai, trich_xuat_id,
                   duoc_dung_phan_giai, loai_du_lieu)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                [
                    (
                        m.moc_id,
                        hd,
                        m.loai_moc,
                        m.gia_tri_raw,
                        m.ngay,
                        m.ngay.year if m.ngay else None,
                        m.do_chinh_xac,
                        m.trang_thai,
                        m.trich_xuat_id,
                        m.duoc_dung_phan_giai,
                        LOAI_DU_LIEU,
                    )
                    for m in profile.time_markers
                ],
            )

            cur.executemany(
                """INSERT INTO runtime.vien_dan_phap_ly_hop_dong (vien_dan_id, hop_dong_id,
                   so_hieu, ten_van_ban, noi_dung_vien_dan_mau, trang_thai_trich_xuat,
                   loai_du_lieu, thong_tin_chuan_hoa_json)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                [
                    (
                        c.vien_dan_id,
                        hd,
                        c.so_hieu,
                        c.ten_van_ban,
                        c.raw_text,
                        c.status,
                        LOAI_DU_LIEU,
                        Jsonb(
                            {
                                **c.to_contract().normalized.model_dump(mode="json"),
                                "diem": c.diem,
                                "provenance": c.provenance,
                                "extraction_version": version,
                            }
                        ),
                    )
                    for c in extraction.citations
                ],
            )
            positions = [
                (
                    f"{c.vien_dan_id}_VT{i}",
                    c.vien_dan_id,
                    m.doan_id,
                    LOAI_DU_LIEU,
                    m.quote,
                    m.start,
                    m.end,
                    "EXACT_OFFSET",
                )
                for c in extraction.citations
                for i, m in enumerate(c.mentions, start=1)
            ]
            cur.executemany(
                """INSERT INTO runtime.bang_chung_vien_dan (lien_ket_id, vien_dan_id, doan_id,
                   loai_du_lieu, trich_dan_nguyen_van, ky_tu_bat_dau, ky_tu_ket_thuc,
                   trang_thai_dinh_vi) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT DO NOTHING""",
                positions,
            )

            written, note = self._save_profile(conn, extraction, replace_profile)

        return SaveReport(
            hop_dong_id=hd,
            version=version,
            chunks=len(chunk_rows),
            facts=len(profile.facts),
            evidence=len(profile.evidence),
            subjects=len(profile.subjects),
            markers=len(profile.time_markers),
            citations=len(extraction.citations),
            citation_positions=len(positions),
            profile_written=written,
            profile_note=note,
        )

    def _save_profile(self, conn, extraction: DocumentExtraction, replace: bool):
        hd = extraction.case.hop_dong_id
        profile = extraction.result.contract_profile
        fields = profile.profile.model_dump()
        date_fact = next(
            (f for f in profile.facts if f.ten_truong == "profile.ngay_giao_ket"), None
        )
        evidence = {e.bang_chung_id: e for e in profile.evidence}
        values = {
            **{k: fields.get(k) for k in PROFILE_COLUMNS},
            **{k: _flag(fields.get(k)) for k in TEXT_FLAG_COLUMNS},
            "doan_bang_chung_ngay_id": (
                evidence[date_fact.evidence_ids[0]].doan_id if date_fact else None
            ),
            "trang_thai_profile": TRANG_THAI_PROFILE,
            "loai_du_lieu": LOAI_DU_LIEU,
        }
        exists = conn.execute(
            "SELECT 1 FROM runtime.ho_so_hop_dong WHERE hop_dong_id = %s", (hd,)
        ).fetchone()
        if exists and not replace:
            return False, "Profile đã có (vd dữ liệu seed): giữ nguyên, không ghi đè"
        columns = ", ".join(PROFILE_COLUMNS)
        placeholders = ", ".join(f"%({k})s" for k in PROFILE_COLUMNS)
        if exists:
            assignments = ", ".join(f"{k} = %({k})s" for k in PROFILE_COLUMNS)
            conn.execute(
                f"UPDATE runtime.ho_so_hop_dong SET {assignments} WHERE hop_dong_id = %(hd)s",
                {**values, "hd": hd},
            )
            return True, "Đã ghi đè profile cũ"
        conn.execute(
            f"INSERT INTO runtime.ho_so_hop_dong (hop_dong_id, {columns}) "
            f"VALUES (%(hd)s, {placeholders})",
            {**values, "hd": hd},
        )
        return True, "Đã tạo profile mới"
