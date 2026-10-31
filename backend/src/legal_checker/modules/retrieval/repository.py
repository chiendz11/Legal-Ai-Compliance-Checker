"""SQL inputs and seeded evidence for Retrieval module development."""

from legal_checker.core.postgres import connect_postgres


class RetrievalDatasetRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def load_input_rows(self, ca_id: str) -> dict:
        """C05 source rows and this contract's chunks. DTO mapping remains explicit."""
        with connect_postgres(self.database_url) as connection:
            # Ca đánh giá
            case = connection.execute(
                "SELECT * FROM runtime.ca_danh_gia WHERE ca_id=%s", (ca_id,)
            ).fetchone()
            if case is None:
                raise KeyError(f"Unknown assessment case {ca_id}")
            # yêu cầu áp dụng nối với phiên bản yêu cầu (nếu có)
            requirements = connection.execute(
                """
                SELECT a.*, to_jsonb(v) AS requirement_version
                FROM runtime.yeu_cau_ap_dung a
                LEFT JOIN knowledge.phien_ban_yeu_cau v USING (requirement_version_id)
                WHERE a.ca_id=%s ORDER BY a.yeu_cau_ca_id
            """,
                (ca_id,),
            ).fetchall()
            # Các đoạn hợp đồng của ca đánh giá
            chunks = connection.execute(
                """
                SELECT * FROM runtime.doan_hop_dong
                WHERE hop_dong_id=%s ORDER BY thu_tu, doan_id
            """,
                (case["hop_dong_id"],),
            ).fetchall()
            # tiêu chí đánh giá áp dụng cho các yêu cầu áp dụng của ca đánh giá
            criteria = connection.execute(
                """
                SELECT a.yeu_cau_ca_id, c.*
                FROM runtime.yeu_cau_ap_dung a
                JOIN knowledge.tieu_chi_danh_gia c USING (requirement_version_id)
                WHERE a.ca_id=%s ORDER BY a.yeu_cau_ca_id, c.thu_tu, c.tieu_chi_id
            """,
                (ca_id,),
            ).fetchall()
            return {
                "case": case,
                "requirements": requirements,
                "chunks": chunks,
                "criteria": criteria,
            }

    def load_seeded_evidence(self, ca_id: str, lan_chay_id: str) -> list[dict]:
        """Read a single run; never mix another case's chunks or retrieval run."""
        with connect_postgres(self.database_url) as connection:
            # Lấy C06 theo case/run cùng nội dung và vị trí đoạn của đúng hợp đồng cho C07.
            return connection.execute(
                """
                SELECT r.*, d.noi_dung, d.hop_dong_id, d.section_path,
                       d.page_start, d.page_end
                FROM runtime.ket_qua_truy_xuat r
                JOIN runtime.yeu_cau_ap_dung a USING (yeu_cau_ca_id)
                JOIN runtime.ca_danh_gia ca USING (ca_id)
                JOIN runtime.doan_hop_dong d
                  ON d.doan_id=r.doan_id AND d.hop_dong_id=ca.hop_dong_id
                WHERE a.ca_id=%s AND r.lan_chay_id=%s
                ORDER BY r.yeu_cau_ca_id, r.thu_hang, r.truy_xuat_id
            """,
                (ca_id, lan_chay_id),
            ).fetchall()
