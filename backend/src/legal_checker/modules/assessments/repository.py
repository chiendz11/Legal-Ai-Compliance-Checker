"""PostgreSQL writer: normalized workbook tables plus immutable case/run snapshots."""

import json
from datetime import datetime, timezone

from psycopg import sql
from psycopg.types.json import Jsonb

from legal_checker.core.exceptions import ConflictError
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.assessments.audit import digest
from legal_checker.modules.legal_knowledge.repository import canonical
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.pipeline import PipelineRequest, PipelineResponse

OUTPUTS = {
    "ket_qua_tieu_chi": ("criterion_results", "ket_qua_id"),
    "ket_qua_tuan_thu": ("requirement_results", "tuan_thu_id"),
    "ket_qua_rui_ro": ("risks", "ket_qua_rui_ro_id"),
    "khuyen_nghi_danh_gia": ("recommendations", "khuyen_nghi_ca_id"),
}


def pin(request):
    return {
        k: getattr(request, k)
        for k in (
            "phien_ban_id",
            "rule_version",
            "legal_knowledge_version",
            "knowledge_snapshot_sha256",
        )
    }


def insert(connection, schema, table, key, values, json_columns=()):
    """Keep existing identities immutable; conflicting contents roll back the whole run."""
    values = {
        k: json.loads(canonical(v)) if k in json_columns and v is not None else v
        for k, v in values.items()
    }
    columns = list(values)
    params = tuple(
        Jsonb(values[k]) if k in json_columns and values[k] is not None else values[k]
        for k in columns
    )
    query = sql.SQL(
        "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO NOTHING RETURNING {}"
    ).format(
        sql.Identifier(schema, table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        sql.Identifier(key),
        sql.Identifier(key),
    )
    if connection.execute(query, params).fetchone() is None:
        prior = connection.execute(
            sql.SQL("SELECT {} FROM {} WHERE {}=%s").format(
                sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.Identifier(schema, table),
                sql.Identifier(key),
            ),
            (values[key],),
        ).fetchone()
        if dict(prior) != values:
            raise ConflictError(f"Existing {table} identity has different contents")


class Store:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def get(self, ca_id, run_id):
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(
                "SELECT response_json, output_sha256 FROM runtime.assessment_runs "
                "WHERE ca_id=%s AND run_id=%s",
                (ca_id, run_id),
            ).fetchone()
        if row is None:
            return None
        result = PipelineResponse.model_validate(row["response_json"])
        if digest(result) != row["output_sha256"]:
            raise ValueError("Stored assessment output checksum is invalid")
        return result

    def save(self, request: PipelineRequest, response: PipelineResponse):
        if any(getattr(request, k) != getattr(response, k) for k in Context.model_fields):
            raise ValueError("Response context differs from request")
        with connect_postgres(self.database_url) as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (request.ca_id,)
            )
            case = connection.execute(
                "SELECT * FROM runtime.ca_danh_gia WHERE ca_id=%s FOR UPDATE", (request.ca_id,)
            ).fetchone()
            pinned = connection.execute(
                "SELECT pin FROM runtime.assessment_case_pins WHERE ca_id=%s", (request.ca_id,)
            ).fetchone()
            if case and (
                case["hop_dong_id"] != request.payload.hop_dong_id
                or any(
                    case[k] != getattr(request, k)
                    for k in ("phien_ban_id", "rule_version", "legal_knowledge_version")
                )
            ):
                raise ConflictError("Case contract or deployment/knowledge/rule pin cannot change")
            if pinned and pinned["pin"] != pin(request):
                raise ConflictError("Case knowledge snapshot pin cannot change")
            previous = connection.execute(
                "SELECT input_sha256, response_json FROM runtime.assessment_runs "
                "WHERE ca_id=%s AND run_id=%s",
                (request.ca_id, request.run_id),
            ).fetchone()
            if previous:
                if previous["input_sha256"] != digest(request):
                    raise ConflictError("Run ID already exists with a different input")
                return PipelineResponse.model_validate(previous["response_json"])
            if not connection.execute(
                "SELECT 1 FROM knowledge.knowledge_snapshots WHERE sha256=%s",
                (request.knowledge_snapshot_sha256,),
            ).fetchone():
                raise ValueError("Knowledge snapshot must exist in DB before saving a run")
            # Direct steps-5-7 API registers metadata only; it does not invent a source PDF.
            connection.execute(
                "INSERT INTO runtime.hop_dong (hop_dong_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (request.payload.hop_dong_id,),
            )
            connection.execute(
                "INSERT INTO knowledge.phien_ban_trien_khai "
                "(phien_ban_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (request.phien_ban_id,),
            )
            if not case:
                connection.execute(
                    """
                    INSERT INTO runtime.ca_danh_gia
                    (ca_id, hop_dong_id, phien_ban_id, rule_version, legal_knowledge_version,
                     trang_thai, loai_du_lieu) VALUES (%s,%s,%s,%s,%s,'REVIEW_PENDING','API_INPUT')
                """,
                    (
                        request.ca_id,
                        request.payload.hop_dong_id,
                        request.phien_ban_id,
                        request.rule_version,
                        request.legal_knowledge_version,
                    ),
                )
            connection.execute(
                """
                INSERT INTO runtime.assessment_case_pins VALUES (%s,%s,%s) ON CONFLICT DO NOTHING
            """,
                (request.ca_id, Jsonb(pin(request)), request.knowledge_snapshot_sha256),
            )
            self.save_inputs(connection, request)
            connection.execute(
                """
                INSERT INTO runtime.assessment_runs
                (ca_id,run_id,input_sha256,output_sha256,input_json,response_json)
                VALUES (%s,%s,%s,%s,%s,%s)
            """,
                (
                    request.ca_id,
                    request.run_id,
                    digest(request),
                    digest(response),
                    Jsonb(request.model_dump(mode="json")),
                    Jsonb(response.model_dump(mode="json")),
                ),
            )
            self.save_outputs(connection, request, response)
            connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return response

    def save_inputs(self, connection, request):
        for chunk in request.payload.chunks:
            insert(connection, "runtime", "doan_hop_dong", "doan_id", chunk.model_dump())
        for requirement in request.payload.requirements:
            if requirement.moc_id:
                marker = connection.execute(
                    "SELECT hop_dong_id FROM runtime.moc_thoi_gian_hop_dong WHERE moc_id=%s",
                    (requirement.moc_id,),
                ).fetchone()
                if not marker or marker["hop_dong_id"] != request.payload.hop_dong_id:
                    raise ValueError("Requirement time marker is not registered for this contract")
            data = requirement.model_dump()
            data.pop("reason")
            # Mốc ID must refer to a real DI marker, not fabricated by a reasoning request.
            insert(
                connection,
                "runtime",
                "yeu_cau_ap_dung",
                "yeu_cau_ca_id",
                {
                    **data,
                    "ly_do": canonical(requirement.reason),
                },
                ("profile_snapshot_json", "dieu_kien_snapshot_json", "nguon_snapshot_json"),
            )
        for evidence in request.payload.retrieval:
            data = evidence.model_dump()
            scores = data.pop("scores")
            insert(
                connection,
                "runtime",
                "ket_qua_truy_xuat",
                "truy_xuat_id",
                {
                    **data,
                    **{k: scores.get(k) for k in ("bm25_score", "vector_score", "rerank_score")},
                },
            )
        for citation in request.payload.citations:
            connection.execute(
                """
                INSERT INTO runtime.vien_dan_phap_ly_hop_dong (vien_dan_id,hop_dong_id)
                VALUES (%s,%s) ON CONFLICT DO NOTHING
            """,
                (citation.vien_dan_id, request.payload.hop_dong_id),
            )
            owner = connection.execute(
                "SELECT hop_dong_id FROM runtime.vien_dan_phap_ly_hop_dong WHERE vien_dan_id=%s",
                (citation.vien_dan_id,),
            ).fetchone()
            if owner["hop_dong_id"] != request.payload.hop_dong_id:
                raise ConflictError("Citation belongs to a different contract")
            insert(
                connection,
                "runtime",
                "phat_hien_vien_dan",
                "finding_id",
                {
                    "finding_id": citation.finding_id,
                    "ca_id": citation.ca_id,
                    "vien_dan_id": citation.vien_dan_id,
                    "van_ban_id": citation.normalized_van_ban_id,
                    "trang_thai": citation.status,
                    "ly_do": citation.ly_do,
                    "finding_verified": citation.finding_verified,
                    "moc_ap_dung": citation.relevant_date,
                    "domain_status": citation.domain_status,
                    "source_snapshot_json": citation.source_snapshot_json,
                    "lan_chay_id": citation.lan_chay_id,
                    "knowledge_version": citation.knowledge_version,
                    "ma_ly_do": citation.reason_code,
                    "trang_thai_review": "PENDING",
                    "hien_tai_snapshot_json": {
                        "current_status": citation.current_status,
                        "replacement_van_ban_id": citation.replacement_van_ban_id,
                    },
                },
                ("source_snapshot_json", "hien_tai_snapshot_json"),
            )

    def save_outputs(self, connection, request, response):
        now = datetime.now(timezone.utc)
        for result in response.payload.criterion_results:
            values = {
                "ket_qua_id": result.ket_qua_id,
                "ca_id": result.ca_id,
                "tieu_chi_id": result.tieu_chi_id,
                "yeu_cau_ca_id": result.yeu_cau_ca_id,
                "giai_thich": result.giai_thich,
                "loai_phat_hien": result.finding,
                "model_version": result.model_version,
                "prompt_version": result.prompt_version,
                "tieu_chi_snapshot_json": result.tieu_chi_snapshot_json,
                "uncertainty_reason": result.uncertainty_reason,
                "pham_vi_ket_luan": result.pham_vi_ket_luan,
                "lan_chay_id": result.lan_chay_id,
                "review_status": result.review_status,
                "ngay_danh_gia": now,
                **result.gates.model_dump(),
            }
            insert(
                connection,
                "runtime",
                "ket_qua_tieu_chi",
                "ket_qua_id",
                values,
                ("tieu_chi_snapshot_json",),
            )
            for index, evidence in enumerate(result.evidence):
                insert(
                    connection,
                    "runtime",
                    "bang_chung_ket_qua",
                    "lien_ket_id",
                    {
                        "lien_ket_id": f"{result.ket_qua_id}/evidence/{index}",
                        "ket_qua_id": result.ket_qua_id,
                        **evidence.model_dump(),
                    },
                )
            for index, evidence in enumerate(result.external_evidence):
                # External evidence must already be registered with source/support-doc FKs.
                support = connection.execute(
                    "SELECT chung_tu_id FROM runtime.chung_tu_bo_sung "
                    "WHERE ca_id=%s AND tep_id IN "
                    "(SELECT tep_id FROM runtime.tep_nguon WHERE object_uri=%s AND sha256=%s)",
                    (request.ca_id, evidence.object_uri, evidence.sha256),
                ).fetchone()
                if support is None:
                    raise ValueError("External evidence source/support document is not registered")
                insert(
                    connection,
                    "runtime",
                    "bang_chung_ngoai",
                    "lien_ket_id",
                    {
                        "lien_ket_id": f"{result.ket_qua_id}/external/{index}",
                        "ket_qua_id": result.ket_qua_id,
                        "chung_tu_id": support["chung_tu_id"],
                        "trich_dan": evidence.object_uri,
                    },
                )
        for result in response.payload.requirement_results:
            insert(
                connection,
                "runtime",
                "ket_qua_tuan_thu",
                "tuan_thu_id",
                {
                    "tuan_thu_id": result.tuan_thu_id,
                    "yeu_cau_ca_id": result.yeu_cau_ca_id,
                    "nhan": result.status,
                    "so_tieu_chi_ap_dung": result.so_tieu_chi_ap_dung,
                    "so_tieu_chi_da_danh_gia": result.so_tieu_chi_da_danh_gia,
                    "so_unknown": result.so_unknown,
                    "rule_version": result.rule_version,
                    "giai_thich": result.giai_thich,
                    "requirement_snapshot_json": result.requirement_snapshot_json,
                    "ngay_tong_hop": now,
                },
                ("requirement_snapshot_json",),
            )
        for risk in response.payload.risks:
            insert(
                connection,
                "runtime",
                "ket_qua_rui_ro",
                "ket_qua_id",
                {
                    "ket_qua_id": risk.ket_qua_rui_ro_id,
                    "ca_id": risk.ca_id,
                    "rui_ro_id": risk.rui_ro_id,
                    "giai_thich": risk.giai_thich,
                    "quy_tac_id": risk.quy_tac_id,
                    "yeu_cau_ca_id": risk.source.yeu_cau_ca_id,
                    "nguon_tieu_chi_id": risk.source.ket_qua_tieu_chi_id,
                    "nguon_vien_dan_id": risk.source.citation_finding_id,
                    "severity_snapshot": risk.severity,
                    "ten_snapshot": risk.risk_snapshot["ten_rui_ro"],
                    "mo_ta_snapshot": risk.risk_snapshot["mo_ta"],
                    "rule_snapshot_json": risk.rule_snapshot_json,
                    "loai_rui_ro": risk.risk_type,
                },
                ("rule_snapshot_json",),
            )
        for recommendation in response.payload.recommendations:
            data = recommendation.model_dump()
            data["noi_dung_snapshot"] = data.pop("noi_dung")
            data["dieu_kien_snapshot"] = canonical(data["dieu_kien_snapshot"])
            data["evidence_ids_json"] = data.pop("evidence_ids")
            data["legal_basis_ids_json"] = data.pop("legal_basis_ids")
            insert(
                connection,
                "runtime",
                "khuyen_nghi_danh_gia",
                "khuyen_nghi_ca_id",
                data,
                ("evidence_ids_json", "legal_basis_ids_json", "template_snapshot_json"),
            )
        # Original DTOs keep fields absent from workbook columns and unambiguous run membership.
        for table, (attribute, key) in OUTPUTS.items():
            for item in getattr(response.payload, attribute):
                connection.execute(
                    "INSERT INTO runtime.assessment_output_lineage VALUES (%s,%s,%s,%s,%s)",
                    (
                        table,
                        getattr(item, key),
                        request.ca_id,
                        request.run_id,
                        Jsonb(item.model_dump(mode="json")),
                    ),
                )
