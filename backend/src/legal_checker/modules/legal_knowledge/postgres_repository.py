"""Workbook knowledge queries for independent module development.

Returns SQL rows, including source verification flags. Use Knowledge in repository.py
when an engine needs the complete, content-hashed KnowledgeSnapshot interface.
"""

from legal_checker.core.postgres import connect_postgres


class WorkbookKnowledgeRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def criteria_for(self, requirement_version_id: str) -> list[dict]:
        with connect_postgres(self.database_url) as connection:
            return connection.execute(
                """
                SELECT c.*, v.requirement_id, v.source_van_ban_id, v.dieu_khoan_id
                FROM knowledge.tieu_chi_danh_gia c
                JOIN knowledge.phien_ban_yeu_cau v USING (requirement_version_id)
                WHERE c.requirement_version_id = %s
                ORDER BY c.thu_tu, c.tieu_chi_id
            """,
                (requirement_version_id,),
            ).fetchall()

    def decision_rules_for(self, criterion_id: str) -> list[dict]:
        with connect_postgres(self.database_url) as connection:
            return connection.execute(
                """
                SELECT * FROM knowledge.quy_tac_quyet_dinh
                WHERE tieu_chi_id=%s ORDER BY uu_tien DESC, quy_tac_id
            """,
                (criterion_id,),
            ).fetchall()

    def risk_templates_for(self, criterion_id: str) -> list[dict]:
        with connect_postgres(self.database_url) as connection:
            return connection.execute(
                """
                SELECT q.quy_tac_id, q.trigger_json, q.rule_version, q.trang_thai,
                       to_jsonb(r) AS risk, to_jsonb(k) AS recommendation
                FROM knowledge.quy_tac_rui_ro q
                JOIN knowledge.danh_muc_rui_ro r USING (rui_ro_id)
                LEFT JOIN knowledge.rui_ro_khuyen_nghi l USING (rui_ro_id)
                LEFT JOIN knowledge.danh_muc_khuyen_nghi k USING (khuyen_nghi_id)
                WHERE q.tieu_chi_id=%s ORDER BY q.quy_tac_id, k.khuyen_nghi_id
            """,
                (criterion_id,),
            ).fetchall()
