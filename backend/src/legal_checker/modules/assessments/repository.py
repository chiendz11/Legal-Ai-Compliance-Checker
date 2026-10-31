"""PostgreSQL writer: normalized workbook tables plus immutable case/run snapshots."""

import hashlib
import json
from decimal import Decimal
from math import isfinite

from psycopg import sql
from psycopg.types.json import Jsonb

from legal_checker.core.exceptions import ConflictError
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.assessments.audit import digest
from legal_checker.modules.assessments.integrity import (
    validate_membership,
    validate_pinned_knowledge,
)
from legal_checker.modules.compliance.mappers import map_requirement
from legal_checker.modules.legal_knowledge.repository import canonical
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


def score_values(scores):
    """Store the DTO's decimal representation, avoiding float8-to-NUMERIC rounding."""
    values = {}
    for key in ("bm25_score", "vector_score", "rerank_score"):
        value = scores.get(key)
        if value is not None and not isfinite(value):
            raise ValueError("Retrieval scores must be finite")
        values[key] = Decimal(str(value)) if value is not None else None
    return values


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


def checked_model(payload, checksum, model, label):
    """Verify raw stored JSON before adding defaults introduced by newer contracts."""
    actual = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    if actual != checksum:
        raise ValueError(f"Stored assessment {label} checksum is invalid")
    return model.model_validate(payload)


def normalized_output(table, result, produced_at):
    """The single projection used for both writes and historical integrity reads."""
    if table == "ket_qua_tieu_chi":
        return {
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
            "ngay_danh_gia": produced_at,
            **result.gates.model_dump(),
        }, ("tieu_chi_snapshot_json",)
    if table == "ket_qua_tuan_thu":
        return {
            "tuan_thu_id": result.tuan_thu_id,
            "yeu_cau_ca_id": result.yeu_cau_ca_id,
            "nhan": result.status,
            "so_tieu_chi_ap_dung": result.so_tieu_chi_ap_dung,
            "so_tieu_chi_da_danh_gia": result.so_tieu_chi_da_danh_gia,
            "so_unknown": result.so_unknown,
            "rule_version": result.rule_version,
            "giai_thich": result.giai_thich,
            "requirement_snapshot_json": result.requirement_snapshot_json,
            "ngay_tong_hop": produced_at,
        }, ("requirement_snapshot_json",)
    if table == "ket_qua_rui_ro":
        return {
            "ket_qua_id": result.ket_qua_rui_ro_id,
            "ca_id": result.ca_id,
            "rui_ro_id": result.rui_ro_id,
            "giai_thich": result.giai_thich,
            "quy_tac_id": result.quy_tac_id,
            "yeu_cau_ca_id": result.source.yeu_cau_ca_id,
            "nguon_tieu_chi_id": result.source.ket_qua_tieu_chi_id,
            "nguon_vien_dan_id": result.source.citation_finding_id,
            "severity_snapshot": result.severity,
            "ten_snapshot": result.risk_snapshot["ten_rui_ro"],
            "mo_ta_snapshot": result.risk_snapshot["mo_ta"],
            "rule_snapshot_json": result.rule_snapshot_json,
            "loai_rui_ro": result.risk_type,
        }, ("rule_snapshot_json",)
    if table == "khuyen_nghi_danh_gia":
        values = result.model_dump()
        values["noi_dung_snapshot"] = values.pop("noi_dung")
        values["dieu_kien_snapshot"] = canonical(values["dieu_kien_snapshot"])
        values["evidence_ids_json"] = values.pop("evidence_ids")
        values["legal_basis_ids_json"] = values.pop("legal_basis_ids")
        return values, ("evidence_ids_json", "legal_basis_ids_json", "template_snapshot_json")
    raise ValueError("Unknown normalized output table")


def check_normalized_row(connection, table, key, values, json_columns=()):
    expected = {
        name: json.loads(canonical(value)) if name in json_columns and value is not None else value
        for name, value in values.items()
    }
    row = connection.execute(
        sql.SQL("SELECT {} FROM {} WHERE {}=%s").format(
            sql.SQL(", ").join(map(sql.Identifier, expected)),
            sql.Identifier("runtime", table),
            sql.Identifier(key),
        ),
        (expected[key],),
    ).fetchone()
    if row is None or dict(row) != expected:
        raise ValueError(f"Stored normalized {table} differs from the run snapshot")


class Store:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def get(self, ca_id, run_id):
        saved = self._read(ca_id, run_id)
        return saved[1] if saved else None

    def get_input(self, ca_id: str, run_id: str) -> PipelineRequest | None:
        """Read one immutable input, never selecting the latest case run."""
        saved = self._read(ca_id, run_id)
        return saved[0] if saved else None

    def get_lineage(self, ca_id: str, run_id: str) -> list[dict]:
        """Read full C07/C08/C10/C11 DTOs with exact run membership and integrity checks."""
        saved = self._read(ca_id, run_id)
        return saved[2] if saved else []

    def _read(self, ca_id, run_id):
        with connect_postgres(self.database_url) as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = connection.execute(
                "SELECT input_json, input_sha256, response_json, output_sha256 "
                "FROM runtime.assessment_runs "
                "WHERE ca_id=%s AND run_id=%s",
                (ca_id, run_id),
            ).fetchone()
            if row is None:
                return None
            return self._checked_saved(connection, row, ca_id, run_id)

    def _checked_saved(self, connection, row, ca_id, run_id):
        """Validate one stored graph in a single transaction, without running engines."""
        request = checked_model(row["input_json"], row["input_sha256"], PipelineRequest, "input")
        response = checked_model(
            row["response_json"], row["output_sha256"], PipelineResponse, "output"
        )
        if request.ca_id != ca_id or request.run_id != run_id:
            raise ValueError("Stored assessment case/run membership is invalid")
        validate_membership(request, response)
        case = connection.execute(
            "SELECT hop_dong_id, phien_ban_id, rule_version, legal_knowledge_version "
            "FROM runtime.ca_danh_gia WHERE ca_id=%s",
            (ca_id,),
        ).fetchone()
        pinned = connection.execute(
            "SELECT pin, knowledge_sha256 FROM runtime.assessment_case_pins WHERE ca_id=%s",
            (ca_id,),
        ).fetchone()
        if (
            case is None
            or case["hop_dong_id"] != request.payload.hop_dong_id
            or any(
                case[key] != getattr(request, key)
                for key in ("phien_ban_id", "rule_version", "legal_knowledge_version")
            )
            or pinned is None
            or pinned["pin"] != pin(request)
            or pinned["knowledge_sha256"] != request.knowledge_snapshot_sha256
        ):
            raise ValueError("Stored assessment case pin differs from the run snapshot")
        knowledge = connection.execute(
            "SELECT content FROM knowledge.knowledge_snapshots WHERE sha256=%s",
            (request.knowledge_snapshot_sha256,),
        ).fetchone()
        if knowledge is None:
            raise ValueError("Stored assessment knowledge snapshot is missing")
        validate_pinned_knowledge(request, response, knowledge["content"])
        rows = connection.execute(
            "SELECT table_name, output_id, ca_id, run_id, payload "
            "FROM runtime.assessment_output_lineage WHERE ca_id=%s AND run_id=%s "
            "ORDER BY table_name, output_id",
            (ca_id, run_id),
        ).fetchall()
        expected = {
            (table, getattr(item, key)): item.model_dump(mode="json")
            for table, (attribute, key) in OUTPUTS.items()
            for item in getattr(response.payload, attribute)
        }
        actual = {(item["table_name"], item["output_id"]): item["payload"] for item in rows}
        if actual != expected:
            raise ValueError("Stored output lineage differs from the run snapshot")
        self._check_normalized(connection, request, response)
        return request, response, [dict(item) for item in rows]

    def _check_normalized(self, connection, request, response):
        for table, (attribute, output_key) in OUTPUTS.items():
            key = "ket_qua_id" if table == "ket_qua_rui_ro" else output_key
            for item in getattr(response.payload, attribute):
                values, json_columns = normalized_output(table, item, response.produced_at)
                check_normalized_row(connection, table, key, values, json_columns)
        for chunk in request.payload.chunks:
            check_normalized_row(connection, "doan_hop_dong", "doan_id", chunk.model_dump())
        for requirement in request.payload.requirements:
            row = connection.execute(
                "SELECT * FROM runtime.yeu_cau_ap_dung WHERE yeu_cau_ca_id=%s",
                (requirement.yeu_cau_ca_id,),
            ).fetchone()
            if row is None or map_requirement(row) != requirement:
                raise ValueError("Stored normalized requirement differs from the run snapshot")
        for retrieval in request.payload.retrieval:
            values = retrieval.model_dump()
            scores = values.pop("scores")
            values.update(score_values(scores))
            check_normalized_row(connection, "ket_qua_truy_xuat", "truy_xuat_id", values)
        for citation in request.payload.citations:
            check_normalized_row(
                connection,
                "vien_dan_phap_ly_hop_dong",
                "vien_dan_id",
                {"vien_dan_id": citation.vien_dan_id, "hop_dong_id": request.payload.hop_dong_id},
            )
            check_normalized_row(
                connection,
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
        for criterion in response.payload.criterion_results:
            evidence_rows = connection.execute(
                "SELECT lien_ket_id, ket_qua_id, doan_id, trich_dan, ky_tu_bat_dau, ky_tu_ket_thuc "
                "FROM runtime.bang_chung_ket_qua WHERE ket_qua_id=%s ORDER BY lien_ket_id",
                (criterion.ket_qua_id,),
            ).fetchall()
            expected = [
                {
                    "lien_ket_id": f"{criterion.ket_qua_id}/evidence/{index}",
                    "ket_qua_id": criterion.ket_qua_id,
                    **evidence.model_dump(),
                }
                for index, evidence in enumerate(criterion.evidence)
            ]
            if [dict(item) for item in evidence_rows] != sorted(
                expected, key=lambda item: item["lien_ket_id"]
            ):
                raise ValueError("Stored normalized evidence differs from the run snapshot")
            external_rows = connection.execute(
                "SELECT b.lien_ket_id, b.ket_qua_id, b.trich_dan, c.ca_id, "
                "t.object_uri, t.sha256 FROM runtime.bang_chung_ngoai b "
                "JOIN runtime.chung_tu_bo_sung c ON c.chung_tu_id=b.chung_tu_id "
                "JOIN runtime.tep_nguon t ON t.tep_id=c.tep_id "
                "WHERE b.ket_qua_id=%s ORDER BY b.lien_ket_id",
                (criterion.ket_qua_id,),
            ).fetchall()
            expected_external = [
                {
                    "lien_ket_id": f"{criterion.ket_qua_id}/external/{index}",
                    "ket_qua_id": criterion.ket_qua_id,
                    "trich_dan": evidence.object_uri,
                    "ca_id": request.ca_id,
                    "object_uri": evidence.object_uri,
                    "sha256": evidence.sha256,
                }
                for index, evidence in enumerate(criterion.external_evidence)
            ]
            if [dict(item) for item in external_rows] != sorted(
                expected_external, key=lambda item: item["lien_ket_id"]
            ):
                raise ValueError(
                    "Stored normalized external evidence differs from the run snapshot"
                )

    def save(self, request: PipelineRequest, response: PipelineResponse):
        request = PipelineRequest.model_validate(request.model_dump())
        response = PipelineResponse.model_validate(response.model_dump())
        validate_membership(request, response)
        for retrieval in request.payload.retrieval:
            score_values(retrieval.scores)
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
                "SELECT input_json, input_sha256, response_json, output_sha256 "
                "FROM runtime.assessment_runs "
                "WHERE ca_id=%s AND run_id=%s",
                (request.ca_id, request.run_id),
            ).fetchone()
            if previous:
                prior_input = checked_model(
                    previous["input_json"], previous["input_sha256"], PipelineRequest, "input"
                )
                if digest(prior_input) != digest(request):
                    raise ConflictError("Run ID already exists with a different input")
                return self._checked_saved(connection, previous, request.ca_id, request.run_id)[1]
            snapshot = connection.execute(
                "SELECT content FROM knowledge.knowledge_snapshots WHERE sha256=%s",
                (request.knowledge_snapshot_sha256,),
            ).fetchone()
            if not snapshot:
                raise ValueError("Knowledge snapshot must exist in DB before saving a run")
            validate_pinned_knowledge(request, response, snapshot["content"])
            # Internal evaluation registers metadata only; it does not invent a source PDF.
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
            existing = connection.execute(
                "SELECT * FROM runtime.yeu_cau_ap_dung WHERE yeu_cau_ca_id=%s",
                (requirement.yeu_cau_ca_id,),
            ).fetchone()
            if existing is not None:
                # Seed ly_do may be plain text while the DTO carries {summary: text}.
                # Compare the typed projection, preserving every original column/text.
                if map_requirement(existing) != requirement:
                    raise ConflictError("Existing yeu_cau_ap_dung identity has different contents")
                continue
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
                    **score_values(scores),
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
        now = response.produced_at
        for result in response.payload.criterion_results:
            values, json_columns = normalized_output("ket_qua_tieu_chi", result, now)
            insert(
                connection,
                "runtime",
                "ket_qua_tieu_chi",
                "ket_qua_id",
                values,
                json_columns,
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
            values, json_columns = normalized_output("ket_qua_tuan_thu", result, now)
            insert(
                connection,
                "runtime",
                "ket_qua_tuan_thu",
                "tuan_thu_id",
                values,
                json_columns,
            )
        for risk in response.payload.risks:
            values, json_columns = normalized_output("ket_qua_rui_ro", risk, now)
            insert(
                connection,
                "runtime",
                "ket_qua_rui_ro",
                "ket_qua_id",
                values,
                json_columns,
            )
        for recommendation in response.payload.recommendations:
            values, json_columns = normalized_output("khuyen_nghi_danh_gia", recommendation, now)
            insert(
                connection,
                "runtime",
                "khuyen_nghi_danh_gia",
                "khuyen_nghi_ca_id",
                values,
                json_columns,
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
