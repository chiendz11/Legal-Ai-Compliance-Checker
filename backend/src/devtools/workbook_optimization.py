"""Prepare a workbook release for SQL development and explicitly scoped evaluation.

Uses the real engines to build reference outputs, not independent legal gold.
Controlled specifications are authored separately in evaluation_controls.py.
"""

import hashlib
import json
import random
from collections import Counter, defaultdict
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.assessments.repository import Store, insert
from legal_checker.modules.compliance.service import evaluate_compliance
from legal_checker.modules.legal_knowledge.repository import TABLE_KEYS, Knowledge, canonical
from legal_checker.modules.reports.builder import build_draft_report
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.citation import CitationExtraction, CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import (
    Chunk,
    ContractProfile,
    DocumentIntelligenceResult,
    ExtractedFact,
    ProfileEvidence,
    ProfileFields,
    ProfileSubject,
    ProfileTimeMarker,
)
from legal_checker.shared.contracts.handoffs import IntegrationInput, LegalOutput
from legal_checker.shared.contracts.pipeline import PipelineRequest
from legal_checker.shared.contracts.reasoning import ReasoningPayload, ReasoningRequest
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from legal_checker.workflows.steps_5_7 import evaluate
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill
from psycopg import sql
from psycopg.conninfo import make_conninfo

from devtools.database_schema import BY_NAME, TABLES
from devtools.database_seed import WorkbookSeed, seed_database, validate_references
from devtools.evaluation_controls import controlled_cases, verify_control
from devtools.evaluation_documents import document_specifications
from devtools.qa_schema import QA_SHEETS, QA_TABLES
from devtools.qa_validation import validate_qa

VERSION = "v7.5.0-dev-eval-r1"
RELEASE_TIME = datetime(2026, 10, 13, tzinfo=timezone.utc)
DEPLOYMENT = "V750_DEV_EVAL_R1"
OUTPUT_TABLES = (
    "ket_qua_tieu_chi",
    "bang_chung_ket_qua",
    "ket_qua_tuan_thu",
    "ket_qua_rui_ro",
    "khuyen_nghi_danh_gia",
    "bao_cao_danh_gia",
)


@contextmanager
def temporary_database(database_url):
    name = "legal_checker_test_release_" + uuid4().hex
    admin_url = make_conninfo(database_url, dbname="postgres")
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield make_conninfo(database_url, dbname=name)
    finally:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


def artifact(qa, case_id, role, contract_name, record_id, value):
    raw = canonical(value.model_dump(mode="json") if hasattr(value, "model_dump") else value)
    sha = hashlib.sha256(raw.encode()).hexdigest()
    parts = [raw[i : i + 28000] for i in range(0, len(raw), 28000)]
    for number, part in enumerate(parts, 1):
        qa["artifacts"].append(
            {
                "artifact_part_id": f"{case_id}/{role}/{contract_name}/{record_id}/{number}",
                "case_id": case_id,
                "role": role,
                "contract_name": contract_name,
                "record_id": record_id,
                "part_number": number,
                "part_count": len(parts),
                "payload_sha256": sha,
                "content": part,
            }
        )


def split_cases(cases, requirements, chunks, citations, documents, available_sources=None):
    """Fixed, reproducible grouped split, balanced for text length/citations/versions.

    A family is indivisible. Search picks a split using input metadata only, never labels.
    """
    groups = defaultdict(list)
    for case in cases:
        groups[documents[case["hop_dong_id"]]["ho_mau_id"]].append(case["ca_id"])
    versions = defaultdict(set)
    for row in requirements:
        versions[row["ca_id"]].add(row["requirement_version_id"])
    lengths = Counter(r["hop_dong_id"] for r in chunks)
    has_citation = {r["hop_dong_id"] for r in citations}
    features = {}
    for case in cases:
        doc = case["hop_dong_id"]
        n = lengths[doc]
        features[case["ca_id"]] = set(versions[case["ca_id"]]) | {
            "TEXT_" + ("SHORT" if n < 30 else "MEDIUM" if n < 100 else "LONG"),
            "HAS_CITATION" if doc in has_citation else "NO_CITATION",
        }
        if available_sources is not None:
            features[case["ca_id"]].add(
                "ORIGINAL_DOWNLOADED" if doc in available_sources else "ORIGINAL_UNAVAILABLE"
            )
    all_counts = Counter(f for fs in features.values() for f in fs)
    target = (60, 15, 15) if len(cases) == 90 else (len(cases), 0, 0)
    rng = random.Random(750013)
    best = None
    for _ in range(2500 if len(cases) == 90 else 1):
        keys = sorted(groups)
        rng.shuffle(keys)
        parts = [[], [], []]
        # Group allocation minimizes remaining capacity; groups are never split.
        for key in keys:
            options = [i for i in range(3) if len(parts[i]) + len(groups[key]) <= target[i]]
            if not options:
                break
            i = max(options, key=lambda i: target[i] - len(parts[i]))
            parts[i].extend(groups[key])
        if sum(map(len, parts)) != len(cases):
            continue
        score = 0
        for part, t in zip(parts, target, strict=True):
            counts = Counter(f for cid in part for f in features[cid])
            score += sum(
                abs(counts[f] - n * t / len(cases)) / max(n, 1) for f, n in all_counts.items()
            )
            if t:
                score += sum(10 for f, n in all_counts.items() if n >= 6 and not counts[f])
        candidate = (score, parts)
        if best is None or score < best[0]:
            best = candidate
    if best is None:
        raise ValueError("Document families cannot fit requested split sizes")
    return {
        cid: split
        for split, part in zip(("DEV", "VALIDATION", "TEST"), best[1], strict=True)
        for cid in part
    }


def prepare(seed, knowledge, assets_dir, source_audit):
    data = deepcopy(seed.tables)
    qa = {t.name: [] for t in QA_TABLES}
    original_requirements = deepcopy(data["yeu_cau_ap_dung"])
    proposals = {r["tieu_chi_id"] + ":" + r["ca_id"]: r for r in data["ket_qua_tieu_chi"]}
    documents = {r["hop_dong_id"]: r for r in data["hop_dong"]}
    profiles = {r["hop_dong_id"]: r for r in data["ho_so_hop_dong"]}
    real_chunks = {
        r["doan_id"]: r
        for r in data["doan_hop_dong"]
        if r["loai_du_lieu"] == "MAU_HOAC_TAI_LIEU_NGUON_CONG_KHAI"
    }
    # Only source-only evidence can participate in this release.
    data["doan_hop_dong"] = list(real_chunks.values())
    data["embedding_doan_hop_dong"] = [
        r for r in data["embedding_doan_hop_dong"] if r["doan_id"] in real_chunks
    ]
    for name in ("bang_chung_vien_dan", "bang_chung_truong", "bang_chung_ho_so"):
        kept = []
        for row in data[name]:
            chunk = real_chunks.get(row["doan_id"])
            if not chunk:
                continue
            quote = row.get("trich_dan") or row.get("trich_dan_nguyen_van")
            if quote and chunk["noi_dung"].count(quote) == 1:
                start = chunk["noi_dung"].index(quote)
                row.update(ky_tu_bat_dau=start, ky_tu_ket_thuc=start + len(quote))
            elif quote:
                # Retain ambiguous raw text in the original archive, not a fabricated span.
                continue
            kept.append(row)
        data[name] = kept
    citation_ids = {r["vien_dan_id"] for r in data["bang_chung_vien_dan"]}
    data["vien_dan_phap_ly_hop_dong"] = [
        r for r in data["vien_dan_phap_ly_hop_dong"] if r["vien_dan_id"] in citation_ids
    ]
    for row in data["vien_dan_phap_ly_hop_dong"]:
        info = row["thong_tin_chuan_hoa_json"] or {}
        info["position_link_ids"] = [
            e[BY_NAME["bang_chung_vien_dan"].primary_key]
            for e in data["bang_chung_vien_dan"]
            if e["vien_dan_id"] == row["vien_dan_id"]
        ]
        info["source_positions_complete"] = False
        info["source_span_qa_pending"] = True
        row["thong_tin_chuan_hoa_json"] = info
    citation_findings = [r for r in data["phat_hien_vien_dan"] if r["vien_dan_id"] in citation_ids]
    # Remove demo source/support files from active corpus, retaining the original archive.
    data["tep_nguon"] = [r for r in data["tep_nguon"] if r["vai_tro"] == "NGUON_GOC_CONG_KHAI"]
    sources = {r["tep_id"]: r for r in data["tep_nguon"]}
    for check in source_audit:
        row = sources[check["tep_id"]]
        qa["source_checks"].append(
            {
                "tep_id": row["tep_id"],
                "hop_dong_id": row["hop_dong_id"],
                "source_url": row["url_nguon"],
                "status": check["status"],
                "download_sha256": check.get("sha256"),
                "bytes": check.get("bytes"),
                "error": check.get("error"),
            }
        )
        if check.get("sha256"):
            local = Path(check["local_path"])
            target = assets_dir / "original" / local.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(local.read_bytes())
            row.update(
                sha256=check["sha256"],
                mime_type=check["mime_type"],
                object_uri="dataset://v750-r1/sources/original/" + local.name,
                trang_thai_ban_goc="DOWNLOADED_BYTES_NOT_CONTENT_ALIGNED_OR_LEGAL_VERIFIED",
            )

    def change(table, row, updates, reason):
        key = BY_NAME[table].primary_key
        before = {k: row[k] for k in updates}
        row.update(updates)
        qa["change_log"].append(
            {
                "change_id": f"{table}/{row[key]}/{len(qa['change_log'])}",
                "table_name": table,
                "record_id": row[key],
                "reason": reason,
                "before_json": json.loads(canonical(before)),
                "after_json": json.loads(canonical(updates)),
            }
        )

    hypothetical = (
        "ngay_giao_ket",
        "ngay_hieu_luc_hop_dong",
        "ngay_ban_giao_du_kien",
        "gia_tri_hop_dong",
        "la_nha_o_xa_hoi",
        "ben_ban_la_chu_dau_tu",
        "la_nha_xay_moi",
        "ben_ban_la_ca_nhan",
        "ben_mua_la_ca_nhan",
        "bao_lanh_bi_tu_choi_hop_le",
    )
    for row in profiles.values():
        if "SYNTHETIC" in row["trang_thai_profile"]:
            change(
                "ho_so_hop_dong",
                row,
                {
                    **dict.fromkeys(hypothetical),
                    "ben_ban_co_von_nuoc_ngoai": "UNKNOWN",
                    "la_hop_dong_theo_mau": "UNKNOWN",
                    "trang_thai_ngay": "UNKNOWN_SOURCE_DATE",
                    "do_chinh_xac_ngay": "UNKNOWN",
                    "trang_thai_profile": "SILVER_PENDING_SOURCE_REVIEW",
                    "loai_du_lieu": "SILVER_SOURCE_CANDIDATE_NOT_GOLD",
                },
                "Remove illustrative facts; keep raw candidate text",
            )
    for row in data["trich_xuat_truong"]:
        if row["trang_thai"] == "MINH_HOA":
            change(
                "trich_xuat_truong",
                row,
                {
                    "gia_tri_raw": None,
                    "gia_tri_chuan_json": None,
                    "trang_thai": "UNKNOWN",
                    "loai_du_lieu": "REMOVED_ILLUSTRATIVE_VALUE",
                },
                "Illustration is not an extracted fact",
            )
    for row in data["moc_thoi_gian_hop_dong"]:
        row.update(ngay=None, duoc_dung_phan_giai=False, trang_thai="UNKNOWN_SOURCE_DATE")
    for row in data["chu_the_hop_dong"]:
        row.update(la_thuong_nhan="UNKNOWN", la_chu_the_kinh_doanh="UNKNOWN", human_verified=False)
    for case in data["ca_danh_gia"]:
        case.update(
            phien_ban_id=DEPLOYMENT,
            moc_ap_dung=None,
            trang_thai="SILVER_GUARD_REFERENCE_PENDING_HUMAN",
            loai_du_lieu="SILVER_GUARD_REFERENCE",
            profile_snapshot_json={
                "profile": json.loads(canonical(profiles[case["hop_dong_id"]])),
                "source_date_verified": False,
                "scope_complete": False,
                "legal_gold": False,
                "dataset_version": VERSION,
            },
        )
    split = split_cases(
        data["ca_danh_gia"],
        original_requirements,
        list(real_chunks.values()),
        data["vien_dan_phap_ly_hop_dong"],
        documents,
        {r["hop_dong_id"] for r in source_audit if r.get("sha256")},
    )
    source_only = defaultdict(list)
    for row in real_chunks.values():
        source_only[row["hop_dong_id"]].append(row)
    for doc, rows in source_only.items():
        text = "\n\n".join(
            r["noi_dung"] for r in sorted(rows, key=lambda r: (r["thu_tu"] or 0, r["doan_id"]))
        )
        raw = text.encode()
        target = assets_dir / "derived" / f"{doc}.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        row = {k: None for k, _ in BY_NAME["tep_nguon"].columns}
        row.update(
            tep_id="DERIVED_" + doc,
            hop_dong_id=doc,
            vai_tro="DERIVED_TEXT_FOR_TEST_ONLY",
            object_uri="dataset://v750-r1/sources/derived/" + doc + ".txt",
            mime_type="text/plain",
            sha256=hashlib.sha256(raw).hexdigest(),
            ngay_thu_thap=RELEASE_TIME,
            trang_thai_ban_goc="DERIVED_TEXT_NOT_ORIGINAL_PDF",
            ghi_chu="Source chunks only; useful for text module tests, not PDF/OCR gold.",
            loai_du_lieu="DERIVED_SOURCE_TEXT_FOR_TEST",
        )
        data["tep_nguon"].append(row)
    req_by_case = defaultdict(list)
    for row in original_requirements:
        old = {k: row[k] for k in ("scope_status", "version_status", "applicability_status")}
        row.update(
            scope_status="UNKNOWN",
            version_status="UNKNOWN",
            applicability_status="UNKNOWN",
            moc_id=None,
            moc_ap_dung=None,
            phien_ban_id=DEPLOYMENT,
            profile_snapshot_json=json.loads(
                canonical(
                    profiles[
                        documents[
                            next(
                                c["hop_dong_id"]
                                for c in data["ca_danh_gia"]
                                if c["ca_id"] == row["ca_id"]
                            )
                        ]["hop_dong_id"]
                    ]
                )
            ),
            resolution_method="SILVER_CANDIDATE_NORMALIZED_UNKNOWN",
        )
        row["dieu_kien_snapshot_json"].update(
            raw_silver_status=old, normalized_contract_version="1.0"
        )
        req_by_case[row["ca_id"]].append(row)
    candidates = defaultdict(list)
    for row in data["ket_qua_truy_xuat"]:
        if row["doan_id"] in real_chunks:
            candidates[(row["yeu_cau_ca_id"], row["tieu_chi_id"])].append(row)
    for rows in candidates.values():
        rows.sort(key=lambda r: (r["thu_hang"], r["truy_xuat_id"]))
        for number, row in enumerate(rows, 1):
            row.update(thu_hang=number, duoc_chon=number == 1, giai_doan="FINAL")
    for name in (
        *OUTPUT_TABLES,
        "yeu_cau_ap_dung",
        "ket_qua_truy_xuat",
        "phat_hien_vien_dan",
        "chung_tu_bo_sung",
        "bang_chung_ngoai",
        "nhat_ky_goi_llm",
        "nhat_ky_review",
        "phan_quyen_danh_gia",
    ):
        data[name] = []
    deployment = {k: None for k, _ in BY_NAME["phien_ban_trien_khai"].columns}
    deployment.update(
        phien_ban_id=DEPLOYMENT,
        ten_phien_ban=VERSION,
        ngay_tao=RELEASE_TIME,
        legal_snapshot_sha256=knowledge.sha256,
        schema_version="v7.4.9",
        model_reasoning="STRUCTURED_ADAPTER_NO_LLM",
        prompt_version="NOT_USED",
        ghi_chu="Development/evaluation reference, not reviewed legal release.",
        loai_du_lieu="DEV_EVAL_METADATA",
    )
    data["phien_ban_trien_khai"].append(deployment)
    validate_references(WorkbookSeed(seed.source_sha256, data))
    return data, qa, req_by_case, candidates, citation_findings, proposals, split


def profile_dto(data, doc):
    raw = next(r for r in data["ho_so_hop_dong"] if r["hop_dong_id"] == doc)
    values = {k: raw[k] for k in ProfileFields.model_fields if k in raw}
    for key in ("ben_ban_co_von_nuoc_ngoai", "la_hop_dong_theo_mau"):
        values[key] = {"CO": True, "KHONG": False}.get(values[key])
    subjects = [
        ProfileSubject(
            **{
                k: r[k]
                for k in ProfileSubject.model_fields
                if k in r and k not in ("la_thuong_nhan", "la_chu_the_kinh_doanh")
            }
        )
        for r in data["chu_the_hop_dong"]
        if r["hop_dong_id"] == doc
    ]
    markers = [
        ProfileTimeMarker(**{k: r[k] for k in ProfileTimeMarker.model_fields if k in r})
        for r in data["moc_thoi_gian_hop_dong"]
        if r["hop_dong_id"] == doc
    ]
    evidence_rows = [
        r
        for r in data["bang_chung_truong"]
        if r["doan_id"] in {c["doan_id"] for c in data["doan_hop_dong"] if c["hop_dong_id"] == doc}
    ]
    evidence = [
        ProfileEvidence(
            bang_chung_id=r["bang_chung_id"],
            doan_id=r["doan_id"],
            trich_dan=r["trich_dan_nguyen_van"],
            ky_tu_bat_dau=r["ky_tu_bat_dau"],
            ky_tu_ket_thuc=r["ky_tu_ket_thuc"],
        )
        for r in evidence_rows
    ]
    facts = [
        ExtractedFact(**{k: r[k] for k in ExtractedFact.model_fields if k in r})
        for r in data["trich_xuat_truong"]
        if r["hop_dong_id"] == doc
    ]
    for fact in facts:
        fact.evidence_ids = [
            r["bang_chung_id"] for r in evidence_rows if r["trich_xuat_id"] == fact.trich_xuat_id
        ]
    return ContractProfile(
        hop_dong_id=doc,
        profile=values,
        subjects=subjects,
        time_markers=markers,
        facts=facts,
        evidence=evidence,
    )


def document_dto(data, doc):
    chunks = [
        Chunk(**{k: r[k] for k in Chunk.model_fields})
        for r in data["doan_hop_dong"]
        if r["hop_dong_id"] == doc
    ]
    positions = defaultdict(list)
    by_chunk = {r.doan_id: r for r in chunks}
    for r in data["bang_chung_vien_dan"]:
        if r["doan_id"] in by_chunk:
            c = by_chunk[r["doan_id"]]
            positions[r["vien_dan_id"]].append(
                {"doan_id": c.doan_id, "page_start": c.page_start, "page_end": c.page_end}
            )
    citations = []
    for r in data["vien_dan_phap_ly_hop_dong"]:
        if r["hop_dong_id"] == doc:
            info = r["thong_tin_chuan_hoa_json"] or {}
            citations.append(
                CitationExtraction(
                    vien_dan_id=r["vien_dan_id"],
                    hop_dong_id=doc,
                    raw_text=r["noi_dung_vien_dan_mau"] or info["raw_text"],
                    normalized={
                        "so_hieu": info.get("number_normalized") or r["so_hieu"],
                        "ten_van_ban": info.get("document_name_extracted") or r["ten_van_ban"],
                        "loai_van_ban": info.get("document_type_extracted"),
                        "nam": info.get("year_extracted"),
                        "ngay_ban_hanh": info.get("issued_date_extracted"),
                        "dieu": str(info["article_extracted"])
                        if info.get("article_extracted")
                        else None,
                        "khoan": str(info["clause_extracted"])
                        if info.get("clause_extracted")
                        else None,
                    },
                    extraction={"status": "UNKNOWN"},
                    evidence=positions[r["vien_dan_id"]],
                )
            )
    return DocumentIntelligenceResult(
        contract_profile=profile_dto(data, doc), chunks=chunks, citations=citations
    )


def corpus_request(case, data, req_source, candidates, findings, knowledge):
    cid = case["ca_id"]
    run = cid + "_V750_R1_REFERENCE"
    requirements = [
        ApplicableRequirement(
            **{k: r[k] for k in ApplicableRequirement.model_fields if k in r},
            reason={"summary": r["ly_do"], "label_quality": "SILVER_CANDIDATE_NOT_CONFIRMED"},
        )
        for r in req_source
    ]
    retrieval = []
    observations = []
    for requirement in requirements:
        for criterion in knowledge.criteria_for(requirement.requirement_version_id):
            tid = criterion["tieu_chi_id"]
            selected = []
            for r in candidates.get((requirement.yeu_cau_ca_id, tid), []):
                row = {
                    k: r[k]
                    for k in (
                        "truy_xuat_id",
                        "yeu_cau_ca_id",
                        "tieu_chi_id",
                        "doan_id",
                        "giai_doan",
                        "thu_hang",
                        "duoc_chon",
                        "query_text",
                        "retrieval_version",
                        "embedding_model",
                        "index_version",
                        "rerank_model",
                    )
                }
                row.update(
                    lan_chay_id=run,
                    scores={k: r[k] for k in ("bm25_score", "vector_score", "rerank_score")},
                )
                retrieval.append(row)
                if r["duoc_chon"]:
                    chunk = next(c for c in data["doan_hop_dong"] if c["doan_id"] == r["doan_id"])
                    text = chunk["noi_dung"][:300]
                    selected.append(
                        {
                            "doan_id": r["doan_id"],
                            "trich_dan": text,
                            "ky_tu_bat_dau": 0,
                            "ky_tu_ket_thuc": len(text),
                        }
                    )
            observations.append(
                {
                    "tieu_chi_id": tid,
                    "proposed_finding": "UNKNOWN",
                    "giai_thich": (
                        "SILVER: source date/scope/version and relevance remain unverified; "
                        "no legal compliance conclusion."
                    ),
                    "evidence": selected,
                    "local_applicability": "UNKNOWN",
                    "model_version": "STRUCTURED_ADAPTER_NO_LLM",
                    "prompt_version": "NOT_USED",
                }
            )
    citations = [
        CitationValidation(
            **{
                k: r[k]
                for k in CitationValidation.model_fields
                if k in r and k not in ("lan_chay_id",)
            },
            normalized_van_ban_id=r["van_ban_id"],
            relevant_date=None,
            status="UNKNOWN",
            reason_code=r["ma_ly_do"],
            lan_chay_id=run,
        )
        for r in findings
        if r["ca_id"] == cid
    ]
    document = document_dto(data, case["hop_dong_id"])
    request = PipelineRequest(
        ca_id=cid,
        phien_ban_id=DEPLOYMENT,
        rule_version=case["rule_version"],
        legal_knowledge_version=case["legal_knowledge_version"],
        knowledge_snapshot_sha256=knowledge.sha256,
        run_id=run,
        trace_id=cid + "_TRACE_V750_R1",
        payload={
            "hop_dong_id": case["hop_dong_id"],
            "requirements": requirements,
            "retrieval": retrieval,
            "observations": observations,
            "chunks": document.chunks,
            "citations": citations,
        },
    )
    return request, document


def build_release(seed, database_url, assets_dir, source_audit, legal_checks):
    knowledge = Knowledge(database_url)
    source_snapshot = {
        "schema_version": "v7.4.9",
        "tables": {
            name: sorted(seed.tables[name], key=lambda r: r[key])
            for name, key in TABLE_KEYS.items()
        },
    }
    if hashlib.sha256(canonical(source_snapshot).encode()).hexdigest() != knowledge.sha256:
        raise ValueError("Workbook knowledge differs from the selected database knowledge snapshot")
    data, qa, requirements, candidates, findings, proposals, split = prepare(
        seed, knowledge, assets_dir, source_audit
    )
    qa["legal_checks"] = legal_checks
    with temporary_database(database_url) as db_url:
        seed_database(db_url, WorkbookSeed(seed.source_sha256, data))
        # Capture from the new SQL source; no knowledge is loaded from a JSON file.
        sql_knowledge = Knowledge(db_url)
        store = Store(db_url)
        for case in data["ca_danh_gia"]:
            cid = case["ca_id"]
            doc = case["hop_dong_id"]
            request, document = corpus_request(
                case, data, requirements[cid], candidates, findings, sql_knowledge
            )
            response = evaluate(request, sql_knowledge).model_copy(
                update={"produced_at": RELEASE_TIME}
            )
            assert all(r.finding == "UNKNOWN" for r in response.payload.criterion_results)
            assert all(r.status == "INSUFFICIENT" for r in response.payload.requirement_results)
            store.save(request, response)
            context = Context(**request.model_dump(exclude={"contract_name", "payload"}))
            source = next(
                (
                    r
                    for r in data["tep_nguon"]
                    if r["hop_dong_id"] == doc
                    and r["trang_thai_ban_goc"].startswith("DOWNLOADED_BYTES")
                ),
                next(r for r in data["tep_nguon"] if r["tep_id"] == "DERIVED_" + doc),
            )
            assessment = AssessmentCase(
                ca_id=cid,
                hop_dong_id=doc,
                source={
                    k: source[k]
                    for k in ("tep_id", "url_nguon", "object_uri", "mime_type", "sha256")
                },
                assessment_context={"ngay_danh_gia": RELEASE_TIME.date()},
                deployment={
                    k: getattr(context, k)
                    for k in ("phien_ban_id", "rule_version", "legal_knowledge_version")
                },
                tenant_id=case["tenant_id"],
                created_by=case["created_by"],
            )
            scopes = [
                ScopeResolution(
                    **{k: getattr(r, k) for k in ScopeResolution.model_fields if hasattr(r, k)},
                    scope_reason=r.reason["summary"],
                )
                for r in request.payload.requirements
            ]
            reason_request = ReasoningRequest(
                **context.model_dump(),
                payload=ReasoningPayload(**request.payload.model_dump(exclude={"citations"})),
            )
            compliance = evaluate_compliance(reason_request, sql_knowledge)
            report = build_draft_report(
                IntegrationInput(
                    context=context,
                    case=assessment,
                    document=document,
                    legal=LegalOutput(
                        scope=scopes,
                        requirements=request.payload.requirements,
                        citations=request.payload.citations,
                    ),
                    compliance=compliance,
                ),
                sql_knowledge,
            )
            qa["case_manifest"].append(
                {
                    "case_id": cid,
                    "hop_dong_id": doc,
                    "group_id": next(
                        r["ho_mau_id"] for r in data["hop_dong"] if r["hop_dong_id"] == doc
                    ),
                    "split": split[cid],
                    "case_kind": "CORPUS",
                    "label_quality": "SILVER_GUARD_REFERENCE",
                    "dataset_version": VERSION,
                    "label_version": "GUARD_REFERENCE_R1",
                    "knowledge_snapshot_sha256": knowledge.sha256,
                    "module_scope": "C01-C13_DRAFT",
                    "limitations_json": {
                        "legal_gold": False,
                        "original_pdf_ocr_gold": False,
                        "checklist_complete": False,
                        "reference_producer": "CURRENT_DETERMINISTIC_ENGINE",
                        "source_for_intake": source["vai_tro"],
                        "raw_input_sha256": seed.source_sha256,
                    },
                }
            )
            artifact(qa, cid, "INPUT", "PipelineRequest", cid, request)
            artifact(
                qa,
                cid,
                "INPUT",
                "DocumentInput",
                cid,
                {
                    "context": context.model_dump(mode="json"),
                    "case": assessment.model_dump(mode="json"),
                },
            )
            artifact(qa, cid, "EXPECTED", "PipelineResponse", cid, response)
            artifact(qa, cid, "EXPECTED", "C02", doc, document.contract_profile)
            artifact(
                qa,
                cid,
                "EXPECTED",
                "C03",
                doc,
                [r.model_dump(mode="json") for r in document.citations],
            )
            artifact(qa, cid, "EXPECTED", "C04", cid, [r.model_dump(mode="json") for r in scopes])
            for name, rows in [
                ("C05", request.payload.requirements),
                ("C06", request.payload.retrieval),
                ("C07", response.payload.criterion_results),
                ("C08", response.payload.requirement_results),
                ("C09", request.payload.citations),
                ("C10", response.payload.risks),
                ("C11", response.payload.recommendations),
            ]:
                artifact(qa, cid, "EXPECTED", name, cid, [r.model_dump(mode="json") for r in rows])
            artifact(qa, cid, "EXPECTED", "C13", cid, report)
            artifact(
                qa,
                cid,
                "PROPOSAL",
                "LEGACY_SILVER",
                cid,
                [r for r in proposals.values() if r["ca_id"] == cid],
            )
            projected = {
                "ca_id": cid,
                "hop_dong_id": doc,
                "label_quality": "SILVER_GUARD_REFERENCE",
                "typed_c13_artifact": cid + "/EXPECTED/C13/" + cid,
                "input_run_id": request.run_id,
                "criterion_count": len(response.payload.criterion_results),
                "requirement_statuses": [r.status for r in response.payload.requirement_results],
                "citation_statuses": dict(Counter(r.status for r in request.payload.citations)),
                "risk_count": len(response.payload.risks),
                "recommendation_count": len(response.payload.recommendations),
                "legal_gold": False,
                "compliance_score": None,
                "scope_exhaustive": False,
            }
            row = {k: None for k, _ in BY_NAME["bao_cao_danh_gia"].columns}
            row.update(
                bao_cao_id="BC_R1_" + cid,
                ca_id=cid,
                phien_ban_bao_cao=1,
                report_json=projected,
                so_yeu_cau_ung_vien=len(request.payload.requirements),
                so_yeu_cau_da_phan_giai=0,
                so_yeu_cau_da_danh_gia=len(request.payload.requirements),
                mau_so_score=0,
                score_method="NO_SCORE_UNRESOLVED_SCOPE",
                model_version="TEMPLATE_ENGINE_NO_LLM",
                prompt_version="NOT_USED",
                ngay_tao=RELEASE_TIME,
                loai_du_lieu="SILVER_GUARD_REFERENCE",
                report_status="DRAFT",
                review_status="PENDING",
                so_unknown=len(response.payload.criterion_results),
                coverage_ratio=0,
                knowledge_snapshot_sha256=knowledge.sha256,
                rule_version=case["rule_version"],
            )
            with connect_postgres(db_url) as connection:
                insert(
                    connection, "runtime", "bao_cao_danh_gia", "bao_cao_id", row, ("report_json",)
                )
            print("Built reference", cid, flush=True)
        with connect_postgres(db_url) as connection:
            data = {
                t.name: connection.execute(
                    sql.SQL("SELECT * FROM {} ORDER BY {}").format(
                        sql.Identifier(t.schema, t.name), sql.Identifier(t.primary_key)
                    )
                ).fetchall()
                for t in TABLES
            }
    for case in controlled_cases(knowledge):
        verify_control(case, knowledge)
        cid = case["case_id"]
        qa["case_manifest"].append(
            {
                "case_id": cid,
                "hop_dong_id": case["input"]["payload"]["hop_dong_id"],
                "group_id": cid,
                "split": "REGRESSION",
                "case_kind": "CONTROLLED",
                "label_quality": "SYNTHETIC_SPEC",
                "dataset_version": VERSION,
                "label_version": "INDEPENDENT_SPEC_R1",
                "knowledge_snapshot_sha256": knowledge.sha256,
                "module_scope": "C05-C11",
                "limitations_json": {
                    "legal_gold": False,
                    "synthetic": True,
                    "gates_are_assumptions": True,
                    "citation_validation_input_is_oracle": True,
                },
            }
        )
        artifact(qa, cid, "INPUT", "PipelineRequest", cid, case["input"])
        qa["controlled_assertions"].append(
            {
                "case_id": cid,
                "expected_assertions_json": case["expected"],
                "rationale": case["rationale"],
                "legal_review_id": case["legal_review_id"],
            }
        )
        text = case["input"]["payload"]["chunks"][0]["noi_dung"]
        (assets_dir / "controlled").mkdir(parents=True, exist_ok=True)
        (assets_dir / "controlled" / f"{cid}.txt").write_text(text)
    for case in document_specifications(knowledge, assets_dir):
        cid = case["case_id"]
        qa["case_manifest"].append(
            {
                "case_id": cid,
                "hop_dong_id": case["input"].case.hop_dong_id,
                "group_id": cid,
                "split": "REGRESSION",
                "case_kind": "CONTROLLED",
                "label_quality": "SYNTHETIC_SPEC",
                "dataset_version": VERSION,
                "label_version": "LITERAL_EXTRACTION_SPEC_R1",
                "knowledge_snapshot_sha256": knowledge.sha256,
                "module_scope": "DOCUMENTS",
                "limitations_json": {
                    "synthetic": True,
                    "legal_gold": False,
                    "source_pdf_bytes_available": True,
                    "canonical_chunk_ids_are_reference_only": True,
                },
            }
        )
        artifact(qa, cid, "INPUT", "DocumentInput", cid, case["input"])
        artifact(qa, cid, "EXPECTED", "DocumentIntelligenceResult", cid, case["output"])
        artifact(qa, cid, "EXPECTED", "C02", cid, case["output"].contract_profile)
        artifact(
            qa,
            cid,
            "EXPECTED",
            "C03",
            cid,
            [r.model_dump(mode="json") for r in case["output"].citations],
        )
        qa["controlled_assertions"].append(
            {
                "case_id": cid,
                "expected_assertions_json": case["assertions"],
                "rationale": case["rationale"],
                "legal_review_id": None,
            }
        )
    # Tag normalized rows as reference data, not real production executions.
    for name in OUTPUT_TABLES:
        for row in data[name]:
            row["loai_du_lieu"] = "SILVER_GUARD_REFERENCE"
    result = WorkbookSeed(seed.source_sha256, data, qa)
    validate_references(result)
    validate_qa(result)
    return result


def subset_release(seed, splits, hide_expected=False, include_controls=False):
    selected = {
        r["case_id"]
        for r in seed.qa_tables["case_manifest"]
        if r["case_kind"] == "CORPUS" and r["split"] in splits
    }
    docs = {r["hop_dong_id"] for r in seed.tables["ca_danh_gia"] if r["ca_id"] in selected}
    data = deepcopy(seed.tables)
    # Filtering follows the schema's ownership graph; legal knowledge stays common.
    for t in TABLES:
        if t.schema == "runtime":
            rows = data[t.name]
            if any(c == "hop_dong_id" for c, _ in t.columns):
                rows = [r for r in rows if r["hop_dong_id"] in docs]
            if any(c == "ca_id" for c, _ in t.columns):
                rows = [r for r in rows if r["ca_id"] in selected]
            data[t.name] = rows
    from devtools.database_schema import FOREIGN_KEYS

    changed = True
    while changed:
        changed = False
        for source, col, target, key in FOREIGN_KEYS:
            if BY_NAME[source].schema != "runtime":
                continue
            ids = {r[key] for r in data[target]}
            rows = [r for r in data[source] if r[col] is None or r[col] in ids]
            if len(rows) != len(data[source]):
                changed = True
                data[source] = rows
    qa = deepcopy(seed.qa_tables)
    allowed = selected | (
        {r["case_id"] for r in qa["case_manifest"] if r["case_kind"] == "CONTROLLED"}
        if include_controls
        else set()
    )
    qa["case_manifest"] = [r for r in qa["case_manifest"] if r["case_id"] in allowed]
    qa["artifacts"] = [
        r
        for r in qa["artifacts"]
        if r["case_id"] in allowed and (not hide_expected or r["role"] == "INPUT")
    ]
    qa["controlled_assertions"] = [
        r for r in qa["controlled_assertions"] if r["case_id"] in allowed
    ]
    qa["source_checks"] = [r for r in qa["source_checks"] if r["hop_dong_id"] in docs]
    qa["change_log"] = [
        r
        for r in qa["change_log"]
        if r["record_id"]
        in {x[BY_NAME[r["table_name"]].primary_key] for x in data[r["table_name"]]}
    ]
    if hide_expected:
        # Intake-only pack: no DI outputs, chunks, observations or later-module targets.
        for table in TABLES:
            if table.schema == "runtime" and table.name not in (
                "hop_dong",
                "tep_nguon",
                "ca_danh_gia",
            ):
                data[table.name] = []
        for row in data["ca_danh_gia"]:
            row["profile_snapshot_json"] = {"evaluation_mode": "RAW_INPUT_ONLY"}
        qa["change_log"] = []
        qa["controlled_assertions"] = []
        for row in qa["case_manifest"]:
            row["limitations_json"] = {
                "synthetic": row["limitations_json"].get("synthetic", False),
                "legal_gold": False,
                "evaluation_mode": "RAW_INPUT_ONLY",
            }
        qa["artifacts"] = [r for r in qa["artifacts"] if r["contract_name"] == "DocumentInput"]
    result = WorkbookSeed(seed.source_sha256, data, qa)
    validate_references(result)
    validate_qa(result)
    return result


def excel_value(value, kind):
    if value is None:
        return None
    if kind == "JSONB":
        return canonical(value)
    if kind in ("DATE", "TIMESTAMPTZ"):
        return value.isoformat() if isinstance(value, (date, datetime)) else value
    if kind == "NUMERIC":
        return str(value)
    return value


def write_release(seed, path, distribution, *, version=VERSION, synthetic=False, coverage=None):
    workbook = Workbook(write_only=True)
    workbook.properties.title = version + " " + distribution

    def sheet(name, headers, rows):
        ws = workbook.create_sheet(name)
        ws.freeze_panes = "A2"
        for i, header in enumerate(headers, 1):
            from openpyxl.utils import get_column_letter

            ws.column_dimensions[get_column_letter(i)].width = 30 if "json" not in header else 45
        cells = []
        for header in headers:
            cell = WriteOnlyCell(ws, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="0F766E")
            cells.append(cell)
        ws.append(cells)
        for row in rows:
            for value in row:
                if isinstance(value, str) and len(value) > 32767:
                    raise ValueError(
                        f"Excel cell exceeds 32767 characters in {name}; use QA multipart"
                    )
            # Force source strings to text: untrusted document cells are never Excel formulas.
            cells = []
            for value in row:
                cell = WriteOnlyCell(ws, value=value)
                if isinstance(value, str):
                    cell.data_type = "s"
                cells.append(cell)
            ws.append(cells)
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"

    guide = [
        ["Phiên bản", version],
        ["Distribution", distribution],
        ["Runtime cases", len(seed.tables["ca_danh_gia"])],
        ["Quality", "SILVER_GUARD_REFERENCE + separate SYNTHETIC_SPEC; NO LEGAL GOLD"],
        [
            "Knowledge SHA256",
            next(iter(seed.qa_tables["case_manifest"]), {}).get("knowledge_snapshot_sha256", ""),
        ],
        ["90-case split", "60 DEV / 15 VALIDATION / 15 TEST; same split for all modules"],
        ["Master", "Evaluator/maintainer only. DEV pack excludes TEST cases and labels."],
        ["Test inputs", "Only C01 source/input references; target outputs absent."],
        [
            "C01 source",
            "DERIVED_TEXT has real bytes/hash; original PDFs only where download succeeded.",
        ],
        [
            "Reference outputs",
            "Built by current deterministic engine, not independent legal accuracy labels.",
        ],
        ["Controlled suite", "Independent behavior assertions; synthetic facts/gates only."],
        ["Review", "Human/date/scope/source legal approvals remain pending."],
        [
            "Artifacts",
            "QA_ARTIFACTS content fragments concatenate by part_number; verify payload_sha256.",
        ],
        ["C13", "bao_cao_danh_gia is a compact projection. Full typed C13 in QA_ARTIFACTS."],
        ["DB", "50 business tables + QA schema; seed each workbook into a separate fresh DB."],
    ]
    if synthetic:
        guide = [
            ["Phiên bản", version],
            ["Distribution", distribution],
            ["Runtime cases", len(seed.tables["ca_danh_gia"])],
            ["Mode", "SYNTHETIC_EVALUATION; facts/dates/gates are scenario assumptions"],
            ["Quality", "SYNTHETIC_SPEC; authored assertions; no human legal approval"],
            ["Knowledge SHA256", guide[4][1]],
            ["Split", "60 DEV / 15 VALIDATION / 15 TEST; all developers use the same DEV pack"],
            ["Source", "Generated Vietnamese text PDFs and matching UTF-8 text; actual bytes/SHA"],
            [
                "C05",
                "Selected-family reference resolver; production services still need development",
            ],
            ["C07/C08", "Scenario assertions authored before engine execution; compare both"],
            ["Review", "All human_verified=false; reports DRAFT and review PENDING"],
            ["C13", "Full typed report in QA_ARTIFACTS; native report table is compact"],
            ["Scope", "Nine selected requirement families; not an exhaustive legal checklist"],
            ["Test inputs", "No module outputs, assertions, scenario names or target labels"],
        ]
    sheet("QA_README", ["muc", "noi_dung"], guide)
    sheet(
        "BANG_VA_SO_DONG",
        ["ten_bang", "so_dong", "nhom", "cach_su_dung"],
        [[t.name, len(seed.tables[t.name]), t.schema, "BUSINESS"] for t in TABLES],
    )
    sheet(
        "QA_SPLIT_SUMMARY",
        ["split", "case_kind", "so_ca"],
        [
            [a, b, n]
            for (a, b), n in sorted(
                Counter(
                    (r["split"], r["case_kind"]) for r in seed.qa_tables["case_manifest"]
                ).items()
            )
        ],
    )
    todo = [
        [
            "Document Intelligence",
            "Independent OCR/profile annotation; align downloaded file with source text",
            "TEXT_REFERENCE_ONLY",
        ],
        [
            "Scope/Temporal",
            "Verify date/scope/transition for corpus cases; complete checklist",
            "UNKNOWN_GUARD_PATH",
        ],
        [
            "Retrieval",
            "Independent relevance annotation; production embeddings",
            "LEXICAL_REFERENCE_NOT_RELEVANCE_GOLD",
        ],
        [
            "Compliance/Risk/Recommendation",
            "Human legal review for corpus; synthetic assertions for branch coverage",
            "SILVER_AND_SYNTHETIC_REGRESSION",
        ],
        [
            "Review/Report",
            "Authorization/publishing implementation; real review records",
            "DRAFT_SCHEMA_REFERENCE",
        ],
    ]
    if synthetic:
        todo = [
            [
                "Document Intelligence",
                "Implement parser/OCR and compare source PDF fields",
                "SOURCE_ALIGNED_SYNTHETIC_TEXT_PDF_NOT_SCAN",
            ],
            [
                "Scope/Temporal",
                "Implement production resolver; selected-family oracle available",
                "SYNTHETIC_DATE_SCOPE_TRANSITION_SCENARIOS",
            ],
            [
                "Retrieval",
                "Implement retriever/embeddings; use seeded relevance as reference",
                "AUTHORED_RELEVANCE_ORACLE",
            ],
            [
                "Compliance/Risk/Recommendation",
                "Implement LLM adapter and evaluate authored specs",
                "SYNTHETIC_SELECTED_FAMILY_EVALUATION",
            ],
            [
                "Review/Report",
                "Implement review/auth/publish; sources are fictional",
                "DRAFT_ONLY_PENDING_REVIEW",
            ],
        ]
    sheet("QA_TODO", ["module", "can_bo_sung", "current_eligibility"], todo)
    if coverage is not None:
        sheet("QA_COVERAGE", ["metric", "split", "label", "count"], coverage)
    for t in TABLES:
        sheet(
            t.name,
            [k for k, _ in t.columns],
            [[excel_value(r[k], kind) for k, kind in t.columns] for r in seed.tables[t.name]],
        )
    for name, t in QA_SHEETS.items():
        sheet(
            name,
            [k for k, _ in t.columns],
            [
                [excel_value(r[k], kind) for k, kind in t.columns]
                for r in seed.qa_tables.get(t.name, [])
            ],
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def package_distribution(
    root,
    filename,
    seed,
    tag,
    *,
    prefix="dataset://v750-r1/",
    archive_prefix="legal_compliance_v750",
):
    """Only the selected workbook and its referenced sources enter each archive."""
    from zipfile import ZIP_DEFLATED, ZipFile

    members = {Path(filename), Path("README_SU_DUNG.md")}
    for row in seed.tables["tep_nguon"]:
        uri = row["object_uri"]
        if uri and uri.startswith(prefix):
            members.add(Path(uri.removeprefix(prefix)))
    for row in seed.qa_tables["case_manifest"]:
        if row["case_kind"] == "CONTROLLED":
            members.add(Path("sources/controlled") / (row["case_id"] + ".txt"))
    for row in seed.qa_tables["artifacts"]:
        if (
            row["role"] == "INPUT"
            and row["contract_name"] == "DocumentInput"
            and row["part_count"] == 1
        ):
            uri = json.loads(row["content"])["case"]["source"]["object_uri"]
            if uri and uri.startswith(prefix):
                members.add(Path(uri.removeprefix(prefix)))
    destination = root.parent / f"{archive_prefix}_{tag}.zip"
    with ZipFile(destination, "w", ZIP_DEFLATED) as bundle:
        for member in sorted(members):
            path = root / member
            if not path.is_file():
                raise ValueError("Referenced source asset missing: " + str(member))
            bundle.write(path, member)
    return destination
