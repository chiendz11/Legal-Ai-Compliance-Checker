"""Build source-aligned synthetic SQL fixtures and independent scenario assertions."""

import hashlib
import json
import random
import re
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO

from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.assessments.repository import Store, insert
from legal_checker.modules.compliance.service import evaluate_compliance
from legal_checker.modules.legal_knowledge.repository import TABLE_KEYS, Knowledge, canonical
from legal_checker.modules.reports.builder import build_draft_report
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import DocumentIntelligenceResult
from legal_checker.shared.contracts.handoffs import IntegrationInput, LegalOutput
from legal_checker.shared.contracts.pipeline import PipelineRequest
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.workflows.steps_5_7 import evaluate
from psycopg import sql

from devtools.database_schema import BY_NAME, TABLES
from devtools.database_seed import WorkbookSeed, insert_table, seed_database, validate_references
from devtools.qa_schema import QA_TABLES
from devtools.qa_validation import validate_qa
from devtools.synthetic_scenarios import (
    DEPLOYMENT,
    URI_PREFIX,
    VERSION,
    authored_aggregate,
    authored_finding,
    criterion_topic,
    reference_requirements,
    scenario_plan,
    source_sha,
)
from devtools.workbook_optimization import OUTPUT_TABLES, artifact, temporary_database

RELEASE_TIME = datetime(2026, 10, 14, tzinfo=timezone.utc)


def native_row(table, **values):
    row = dict.fromkeys(k for k, _ in BY_NAME[table].columns)
    if set(values) - row.keys():
        raise ValueError("Unknown native columns: " + str(set(values) - row.keys()))
    return {**row, **values}


def render_dossier(scenario, font_path):
    """Embed a Vietnamese font and return real PDF bytes plus chunk/page positions.

    No outcome/scenario code/criterion IDs are printed in the source dossier.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    if not font_path.is_file():
        raise ValueError("Provide --font-path to a Unicode Vietnamese TrueType font")
    pdfmetrics.registerFont(TTFont("SyntheticVietnamese", str(font_path)))
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, invariant=1)
    pdf.setTitle(f"Hồ sơ hợp đồng giả lập {scenario.index:03d}")
    width, height = A4
    page, y = 1, height - 60
    chunks = []
    sections = list(scenario.sections.items())
    head = sections[:2]
    body = sections[2:]
    random.Random(scenario.case_id + scenario.split).shuffle(body)
    for topic, text in head + body:
        words, lines, line = text.split(), [], ""
        for word in words:
            proposed = (line + " " + word).strip()
            if pdfmetrics.stringWidth(proposed, "SyntheticVietnamese", 10) > width - 100:
                lines.append(line)
                line = word
            else:
                line = proposed
        lines.append(line)
        if y - len(lines) * 15 < 55:
            pdf.showPage()
            page, y = page + 1, height - 60
        pdf.setFont("SyntheticVietnamese", 10)
        for line in lines:
            pdf.drawString(50, y, line)
            y -= 15
        y -= 12
        chunks.append(
            {
                "doan_id": scenario.case_id + "_SRC_" + topic.upper(),
                "hop_dong_id": scenario.document_id,
                "noi_dung": text,
                "page_start": page,
                "page_end": page,
            }
        )
    pdf.save()
    return buffer.getvalue(), chunks


def citation_reference(s, context, chunk, knowledge):
    """Source/identity/date predicate on the authored citation, not an assigned random label."""
    document = next(
        (
            v
            for v in knowledge.documents.values()
            if s.citation_number is not None and v["so_hieu"] == s.citation_number
        ),
        None,
    )
    relevant = s.markers["SIGNING"]
    if document is None or relevant is None:
        status, code = "UNKNOWN", "IDENTITY_OR_RELEVANT_DATE_UNRESOLVED"
    elif document["ten_van_ban"] != s.citation_title:
        status, code = "INVALID", "DOCUMENT_NUMBER_TITLE_MISMATCH"
    elif document["hieu_luc_tu"] and relevant < date.fromisoformat(document["hieu_luc_tu"]):
        status, code = "INVALID", "NOT_YET_EFFECTIVE_AT_RELEVANT_DATE"
    elif document["hieu_luc_den"] and relevant >= date.fromisoformat(document["hieu_luc_den"]):
        status, code = "STALE", "EXPIRED_AT_RELEVANT_DATE_NO_TRANSITION_IN_SCENARIO"
    else:
        status, code = "VALID", "IDENTITY_AND_RELEVANT_DATE_MATCH"
    if s.name == "TRANSITION_UNRESOLVED" and status == "STALE":
        status, code = "UNKNOWN", "TRANSITION_CONTEXT_UNRESOLVED"
    cid = s.case_id + "_CITATION"
    extraction = {
        "vien_dan_id": cid,
        "hop_dong_id": s.document_id,
        "raw_text": chunk["noi_dung"],
        "normalized": {"so_hieu": s.citation_number, "ten_van_ban": s.citation_title},
        "extraction": {"status": "EXTRACTED" if s.citation_number else "AMBIGUOUS"},
        "evidence": [{k: chunk[k] for k in ("doan_id", "page_start", "page_end")}],
    }
    finding = CitationValidation(
        finding_id=s.case_id + "_CIT_FINDING",
        ca_id=s.case_id,
        vien_dan_id=cid,
        normalized_van_ban_id=document["van_ban_id"] if document else None,
        relevant_date=relevant,
        status=status,
        reason_code=code,
        ly_do=f"Synthetic reference: {code}; comparison is at the declared event date.",
        domain_status="MATCH" if document else "UNKNOWN",
        finding_verified=status != "UNKNOWN",
        current_status=document["trang_thai"] if document else None,
        replacement_van_ban_id=document["van_ban_thay_the_id"] if document else None,
        source_snapshot_json={
            "synthetic": True,
            "human_approved": False,
            "review_kind": "LIMITED_OFFICIAL_SOURCE_CHECK_WITH_SCENARIO_ASSUMPTIONS",
            "reviewed_knowledge": status != "UNKNOWN",
            "identity_confirmed": document is not None
            and document["ten_van_ban"] == s.citation_title,
            "temporal_source_complete": relevant is not None,
            "transition_context_resolved": s.name != "TRANSITION_UNRESOLVED",
            "official_evidence_required": True,
            "identity_or_context_invalidity_proven": status == "INVALID",
            "evidence_ids": [chunk["doan_id"]],
            "source_document": document,
        },
        lan_chay_id=context.run_id,
        knowledge_version=context.legal_knowledge_version,
    )
    return extraction, finding


def compile_case(s, knowledge, assets_dir, font_path, data):
    """Build literal source data and module handoffs before calling any business engine."""
    context = Context(
        ca_id=s.case_id,
        phien_ban_id=DEPLOYMENT,
        rule_version="CAN_HO_SEED_RULES_20261007",
        legal_knowledge_version="V749_LEGAL_KNOWLEDGE_PENDING_HUMAN",
        knowledge_snapshot_sha256=knowledge.sha256,
        run_id=s.case_id + "_SYN_R2_REFERENCE",
        trace_id=s.case_id + "_SYN_R2_TRACE",
    )
    raw_pdf, chunks = render_dossier(s, font_path)
    path = assets_dir / "synthetic" / (s.case_id + ".pdf")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw_pdf)
    full_text = "\n\n".join(c["noi_dung"] for c in chunks)
    path.with_suffix(".txt").write_text(full_text, encoding="utf-8")
    sha = hashlib.sha256(raw_pdf).hexdigest()
    source_id = s.case_id + "_PDF"
    source = {
        "tep_id": source_id,
        "object_uri": URI_PREFIX + "sources/synthetic/" + path.name,
        "mime_type": "application/pdf",
        "sha256": sha,
    }
    assessment = AssessmentCase(
        ca_id=s.case_id,
        hop_dong_id=s.document_id,
        source=source,
        assessment_context={
            "ngay_danh_gia": "2024-06-15" if s.name == "HISTORICAL_VALID" else "2024-12-15",
            "moc_ap_dung": s.markers["SIGNING"],
            "loai_moc_ap_dung": "NGAY_GIAO_KET",
        },
        deployment={
            k: getattr(context, k)
            for k in ("phien_ban_id", "rule_version", "legal_knowledge_version")
        },
        tenant_id="SYNTHETIC_LOCAL_DEV",
        created_by="SYNTHETIC_SCENARIO_AUTHOR",
    )
    data["hop_dong"].append(
        native_row(
            "hop_dong",
            hop_dong_id=s.document_id,
            ho_mau_id=s.source_group,
            ten_tai_lieu=f"Hồ sơ hợp đồng giả lập {s.index:03d}",
            loai_nguon="AUTHORED_SYNTHETIC_DOSSIER",
            tep_nguon_id=source_id,
            sha256_toan_van=source_sha(full_text),
            sha256_tep_nguon=sha,
            ngay_thu_thap=RELEASE_TIME,
            trang_thai_text="MATCHING_SYNTHETIC_TEXT_PDF",
            xac_minh_giao_dich_thuc_te="SYNTHETIC_NOT_REAL_TRANSACTION",
            trang_thai_dedup="UNIQUE_SOURCE_CASE_INSTANCE",
            loai_tai_lieu="SYNTHETIC_TEST_DOSSIER",
            trang_thai_xu_ly="REFERENCE_READY",
            loai_du_lieu="SYNTHETIC_EVALUATION",
            nhom_nguon_corpus="SYNTHETIC_V750_R2",
            snapshot_nhap_corpus=VERSION,
            sha256_noi_dung_corpus=source_sha(full_text),
        )
    )
    data["tep_nguon"].append(
        native_row(
            "tep_nguon",
            **source,
            hop_dong_id=s.document_id,
            vai_tro="SYNTHETIC_CONTRACT_WITH_RECEIPT_ANNEXES",
            ngay_thu_thap=RELEASE_TIME,
            trang_thai_ban_goc="GENERATED_BYTES_SOURCED_TO_SCENARIO",
            ghi_chu="All source content is fictional; no original contract was rewritten.",
            loai_du_lieu="SYNTHETIC_EVALUATION",
        )
    )
    data["tep_nguon"].append(
        native_row(
            "tep_nguon",
            tep_id=s.case_id + "_TEXT",
            hop_dong_id=s.document_id,
            object_uri=URI_PREFIX + "sources/synthetic/" + s.case_id + ".txt",
            mime_type="text/plain",
            sha256=source_sha(full_text),
            vai_tro="MATCHING_SYNTHETIC_TEXT",
            ngay_thu_thap=RELEASE_TIME,
            trang_thai_ban_goc="CANONICAL_SYNTHETIC_TEXT",
            loai_du_lieu="SYNTHETIC_EVALUATION",
        )
    )
    by_topic = {c["doan_id"].split("_SRC_")[1].lower(): c for c in chunks}
    for i, c in enumerate(chunks, 1):
        data["doan_hop_dong"].append(
            native_row(
                "doan_hop_dong",
                **c,
                section_path=f"Hồ sơ/{i}",
                thu_tu=i,
                chunk_quality="SYNTHETIC_LITERAL_TEXT",
                sha256_text=source_sha(c["noi_dung"]),
                phien_ban_chunk=VERSION,
                loai_du_lieu="SYNTHETIC_SOURCE",
            )
        )
        terms = Counter(re.findall(r"\w+", c["noi_dung"].lower()))
        data["embedding_doan_hop_dong"].append(
            native_row(
                "embedding_doan_hop_dong",
                embedding_id=c["doan_id"] + "_LEXICAL",
                doan_id=c["doan_id"],
                embedding_model="LEXICAL_REFERENCE_NO_DENSE_VECTOR",
                so_chieu=0,
                embedding_json={"terms": dict(terms)},
                sha256_text=source_sha(c["noi_dung"]),
                index_version=VERSION,
                ngay_tao=RELEASE_TIME,
                loai_du_lieu="SYNTHETIC_LEXICAL_INDEX_REFERENCE",
            )
        )
    facts, evidence, subjects = [], [], []

    def fact(name, value, chunk, quote=None):
        fid = s.case_id + "_FACT_" + name
        raw = quote or (str(value) if value is not None else None)
        ids = []
        if chunk is not None:
            raw = quote or chunk["noi_dung"]
            start = chunk["noi_dung"].index(raw)
            eid = fid + "_E"
            span = {
                "doan_id": chunk["doan_id"],
                "trich_dan": raw,
                "ky_tu_bat_dau": start,
                "ky_tu_ket_thuc": start + len(raw),
            }
            evidence.append({"bang_chung_id": eid, **span})
            ids.append(eid)
            data["bang_chung_truong"].append(
                native_row(
                    "bang_chung_truong",
                    bang_chung_id=eid,
                    trich_xuat_id=fid,
                    doan_id=span["doan_id"],
                    trich_dan_nguyen_van=raw,
                    ky_tu_bat_dau=start,
                    ky_tu_ket_thuc=start + len(raw),
                    loai_du_lieu="SYNTHETIC_LITERAL_SPAN",
                )
            )
        value = str(value) if isinstance(value, (date, Decimal)) else value
        status = (
            "CONFLICT"
            if value is None
            and chunk is not None
            and "giá bán" in chunk["noi_dung"]
            and s.conflicting
            else "SYNTHETIC_EXTRACTED"
            if value is not None
            else "UNKNOWN"
        )
        facts.append(
            {
                "trich_xuat_id": fid,
                "ten_truong": name,
                "gia_tri_raw": raw,
                "gia_tri_chuan_json": value,
                "trang_thai": status,
                "phuong_phap": "AUTHORED_SYNTHETIC_REFERENCE",
                "evidence_ids": ids,
            }
        )
        data["trich_xuat_truong"].append(
            native_row(
                "trich_xuat_truong",
                **{k: v for k, v in facts[-1].items() if k != "evidence_ids"},
                hop_dong_id=s.document_id,
                human_verified=False,
                ngay_trich_xuat=RELEASE_TIME,
                loai_du_lieu="SYNTHETIC_EVALUATION",
            )
        )
        return fid

    for role, name in (
        (
            "BEN_BAN",
            f"Ông Trần Minh {s.index:03d}"
            if s.name == "INDIVIDUAL_RESALE"
            else f"Công ty Dự án Giả lập {s.index:03d}",
        ),
        ("BEN_MUA", f"Bà Nguyễn An {s.index:03d}"),
    ):
        subject_id = s.case_id + "_" + role
        business = role == "BEN_BAN" and s.name != "INDIVIDUAL_RESALE"
        subjects.append(
            {
                "chu_the_id": subject_id,
                "vai_tro": role,
                "ten_chu_the": name,
                "loai_chu_the": "DOANH_NGHIEP" if business else "CA_NHAN",
                "la_thuong_nhan": business,
                "la_chu_the_kinh_doanh": business,
                "doan_bang_chung_id": by_topic["parties"]["doan_id"],
            }
        )
        data["chu_the_hop_dong"].append(
            native_row(
                "chu_the_hop_dong",
                **{
                    k: v
                    for k, v in subjects[-1].items()
                    if k not in ("la_thuong_nhan", "la_chu_the_kinh_doanh")
                },
                hop_dong_id=s.document_id,
                la_thuong_nhan="CO" if business else "KHONG",
                la_chu_the_kinh_doanh="CO" if business else "KHONG",
                human_verified=False,
                trang_thai="SYNTHETIC_EXTRACTED",
                ten_raw=name,
                trang_thai_ten="EXTRACTED",
                loai_du_lieu="SYNTHETIC_EVALUATION",
            )
        )
        fact("ten_" + role.lower(), name, by_topic["parties"], name)
    for key, value in s.profile.items():
        topic = (
            "effect"
            if key.startswith("ngay_")
            or key in ("do_chinh_xac_ngay", "trang_thai_ngay", "loai_moc_ap_dung")
            else "price"
            if key in ("gia_tri_hop_dong", "don_vi_tien")
            else "scope"
        )
        if key == "ngay_ban_giao_du_kien":
            topic = "handover"
        if key == "ngay_giao_ket_raw":
            continue
        chunk = by_topic[topic]
        quote = (
            str(value)
            if isinstance(value, (date, Decimal)) and str(value) in chunk["noi_dung"]
            else None
        )
        fact(key, value, chunk, quote)
    numeric_topics = {
        "contract_price": "price",
        "sale_price": "price",
        "first_payment": "first",
        "deposit": "deposit",
        "deposit_included_in_first_payment": "first",
        "prehandover_cumulative": "pre",
        "foreign_seller_art10_4": "scope",
        "foreign_invested_seller": "scope",
        "before_certificate_cumulative": "cert",
        "maintenance_base_price": "price",
        "apartment_value": "price",
        "maintenance_amount": "maintenance",
        "separate_from_sale_price": "maintenance",
        "included_in_sale_payment": "maintenance",
        "warranty_months": "warranty",
        "warranty_start": "warranty",
        "eligible_before_collection": "deposit",
        "sale_price_agreed": "deposit",
    }
    if s.name != "INDIVIDUAL_RESALE":
        for name, topic in numeric_topics.items():
            value = (
                None
                if name
                in ("contract_price", "sale_price", "maintenance_base_price", "apartment_value")
                and s.conflicting
                else s.numeric[name]
            )
            chunk = by_topic[topic]
            quote = str(value) if value is not None and str(value) in chunk["noi_dung"] else None
            fact(name, value, chunk, quote)
    for name, value in (
        ("ma_can_ho", f"A-{s.index:03d}"),
        ("dien_tich_thong_thuy", 60 + s.index % 40),
    ):
        chunk = by_topic.get("property")
        if "property" in s.missing or "property" in s.uncertain:
            value = None
        quote = str(value) if value is not None else None
        fact(name, value, chunk, quote)
    marker_topic = {
        "SIGNING": "effect",
        "COLLECTION": "first",
        "PRE_HANDOVER_COLLECTION": "pre",
        "PRE_CERTIFICATE_COLLECTION": "cert",
    }
    markers = []
    for key, day in s.markers.items():
        fid = fact("moc_" + key, day, by_topic.get(marker_topic[key]))
        marker = {
            "moc_id": s.case_id + "_" + key,
            "loai_moc": key,
            "gia_tri_raw": day.isoformat() if day else "..../..../....",
            "ngay": day,
            "do_chinh_xac": "DAY" if day else "UNKNOWN",
            "trang_thai": "SYNTHETIC_ASSUMPTION" if day else "UNKNOWN",
            "duoc_dung_phan_giai": day is not None,
            "trich_xuat_id": fid,
        }
        markers.append(marker)
        data["moc_thoi_gian_hop_dong"].append(
            native_row(
                "moc_thoi_gian_hop_dong",
                **marker,
                hop_dong_id=s.document_id,
                nam=day.year if day else None,
                ghi_chu="Test assumption, not real signing/performance proof",
                loai_du_lieu="SYNTHETIC_EVALUATION",
            )
        )
    data["ho_so_hop_dong"].append(
        native_row(
            "ho_so_hop_dong",
            **{
                k: v
                for k, v in s.profile.items()
                if k not in ("la_hop_dong_theo_mau", "ben_ban_co_von_nuoc_ngoai")
            },
            hop_dong_id=s.document_id,
            la_hop_dong_theo_mau="CO" if s.profile["la_hop_dong_theo_mau"] else "KHONG",
            ben_ban_co_von_nuoc_ngoai="CO" if s.profile["ben_ban_co_von_nuoc_ngoai"] else "KHONG",
            trang_thai_profile="SYNTHETIC_DECLARED_SCENARIO",
            loai_du_lieu="SYNTHETIC_EVALUATION",
            doan_bang_chung_ngay_id=by_topic["effect"]["doan_id"],
        )
    )
    extraction, citation = citation_reference(s, context, by_topic["citation"], knowledge)
    if citation.status != s.expected_citation:
        raise AssertionError(
            f"{s.case_id}: citation predicate differs from authored scenario: {citation.status} "
            f"vs {s.expected_citation}"
        )
    data["vien_dan_phap_ly_hop_dong"].append(
        native_row(
            "vien_dan_phap_ly_hop_dong",
            vien_dan_id=extraction["vien_dan_id"],
            hop_dong_id=s.document_id,
            so_hieu=s.citation_number,
            ten_van_ban=s.citation_title,
            noi_dung_vien_dan_mau=extraction["raw_text"],
            trang_thai_trich_xuat=extraction["extraction"]["status"],
            thong_tin_chuan_hoa_json=extraction["normalized"],
            loai_du_lieu="SYNTHETIC_EVALUATION",
        )
    )
    citation_chunk = by_topic["citation"]
    data["bang_chung_vien_dan"].append(
        native_row(
            "bang_chung_vien_dan",
            lien_ket_id=extraction["vien_dan_id"] + "_SPAN",
            vien_dan_id=extraction["vien_dan_id"],
            doan_id=citation_chunk["doan_id"],
            trich_dan_nguyen_van=citation_chunk["noi_dung"],
            ky_tu_bat_dau=0,
            ky_tu_ket_thuc=len(citation_chunk["noi_dung"]),
            trang_thai_dinh_vi="EXACT_SYNTHETIC_SPAN",
            loai_du_lieu="SYNTHETIC_EVALUATION",
        )
    )
    document = DocumentIntelligenceResult(
        contract_profile={
            "hop_dong_id": s.document_id,
            "profile": s.profile,
            "subjects": subjects,
            "time_markers": markers,
            "facts": facts,
            "evidence": evidence,
        },
        chunks=chunks,
        citations=[extraction],
    )
    requirements = reference_requirements(s, knowledge)
    retrieval, observations, expected = [], [], {}
    expected_requirements = {}
    for req in requirements:
        criteria = knowledge.criteria_for(req.requirement_version_id)
        if req.applicability_status == "NOT_APPLICABLE":
            continue
        for c in criteria:
            topic = criterion_topic(c)
            chunk = by_topic.get(topic)
            finding = authored_finding(s, req, c)
            expected[c["tieu_chi_id"]] = finding
            # Missing mandatory content has no selected positive evidence.
            selected = chunk is not None and finding != "MISSING"
            candidates = ([chunk] if chunk else []) + [by_topic["cover"], by_topic["method"]]
            seen = set()
            for candidate in candidates:
                if candidate["doan_id"] in seen:
                    continue
                seen.add(candidate["doan_id"])
                retrieval.append(
                    {
                        "truy_xuat_id": req.yeu_cau_ca_id
                        + "_"
                        + c["tieu_chi_id"]
                        + f"_R{len(seen)}",
                        "yeu_cau_ca_id": req.yeu_cau_ca_id,
                        "tieu_chi_id": c["tieu_chi_id"],
                        "doan_id": candidate["doan_id"],
                        "giai_doan": "FINAL",
                        "thu_hang": len(seen),
                        "duoc_chon": selected and candidate is chunk,
                        "query_text": c["noi_dung"],
                        "scores": {},
                        "retrieval_version": "AUTHORED_RELEVANCE_REFERENCE_NOT_RETRIEVER",
                        "index_version": VERSION,
                        "lan_chay_id": context.run_id,
                    }
                )
            numeric_rule = json.loads(
                knowledge.decision(c["tieu_chi_id"], "SATISFIED")["dieu_kien_json"]
            ).get("numeric_rule")
            facts_for_rule = {**s.numeric, "maintenance_base_definition_resolved": True}
            if numeric_rule:
                facts_for_rule["scope"] = numeric_rule.get("scope")
            else:
                facts_for_rule = {}
            observations.append(
                {
                    "tieu_chi_id": c["tieu_chi_id"],
                    "proposed_finding": finding,
                    "giai_thich": (
                        f"Synthetic authored predicate for {c['noi_dung']}; "
                        "literal source clause or declared absence/completeness. "
                        "Not a real transaction finding."
                    ),
                    "gates": {
                        "coverage_complete": s.complete,
                        "absence_verified": s.complete,
                        "evidence_validated": True,
                        "source_verified": True,
                        "scope_confirmed": req.confirmed,
                        "version_resolved": req.confirmed,
                        "exceptions_resolved": True,
                        "evidence_conflict": topic in s.conflicting,
                    },
                    "evidence": [
                        {
                            "doan_id": chunk["doan_id"],
                            "trich_dan": chunk["noi_dung"],
                            "ky_tu_bat_dau": 0,
                            "ky_tu_ket_thuc": len(chunk["noi_dung"]),
                        }
                    ]
                    if selected
                    else [],
                    "local_applicability": "MATCH",
                    "mandatory_confirmed": bool(c["noi_dung_bat_buoc_trong_hd"]),
                    "all_pages_readable": True,
                    "all_related_documents_received": s.complete,
                    "facts": facts_for_rule,
                    "facts_verified": topic not in s.conflicting and topic not in s.uncertain,
                    "model_version": "AUTHORED_SYNTHETIC_PREDICATES_NO_LLM",
                    "prompt_version": "NOT_USED",
                }
            )
        expected_requirements[req.yeu_cau_ca_id] = authored_aggregate(req, criteria, expected)
    request = PipelineRequest(
        **context.model_dump(),
        payload={
            "hop_dong_id": s.document_id,
            "requirements": requirements,
            "chunks": document.chunks,
            "retrieval": retrieval,
            "observations": observations,
            "citations": [citation],
        },
    )
    assertions = {
        "criterion_findings_by_id": expected,
        "requirement_statuses_by_id": expected_requirements,
        "citation_statuses": [s.expected_citation],
        "risk_counts": {
            "COMPLIANCE": sum(f in ("VIOLATED", "MISSING") for f in expected.values()),
            "VERIFICATION": sum(f == "UNKNOWN" for f in expected.values())
            + (citation.status == "UNKNOWN"),
            "CITATION": int(citation.status in ("STALE", "INVALID")),
        },
        "document_fields": json.loads(canonical(s.profile)),
        "requirements": [r.model_dump(mode="json") for r in requirements],
        "relevant_chunk_ids": {
            o["tieu_chi_id"]: [e["doan_id"] for e in o["evidence"]] for o in observations
        },
        "label_authorship": "SCENARIO_PREDICATES_BEFORE_ENGINE_RUN",
        "scope": "NINE_SELECTED_FAMILIES_NOT_EXHAUSTIVE",
    }
    return request, document, assessment, assertions


def assert_synthetic_response(assertions, response):
    actual = {r.tieu_chi_id: r.finding for r in response.payload.criterion_results}
    if actual != assertions["criterion_findings_by_id"]:
        difference = {
            key: (value, actual.get(key))
            for key, value in assertions["criterion_findings_by_id"].items()
            if value != actual.get(key)
        }
        raise AssertionError("Synthetic criterion predicates differ: " + str(difference))
    actual = {r.yeu_cau_ca_id: r.status for r in response.payload.requirement_results}
    if actual != assertions["requirement_statuses_by_id"]:
        raise AssertionError("Synthetic aggregate expectations differ: " + str(actual))
    counts = Counter(r.risk_type for r in response.payload.risks)
    if any(counts[k] != v for k, v in assertions["risk_counts"].items()):
        raise AssertionError(
            f"Synthetic risk routing differs: {counts} vs {assertions['risk_counts']}"
        )
    if any(r.review_status != "PENDING" for r in response.payload.recommendations):
        raise AssertionError("Synthetic data must not fabricate human approval")


def build_synthetic_release(seed, database_url, assets_dir, font_path, split, legal_checks):
    knowledge = Knowledge(database_url)
    source_snapshot = {
        "schema_version": "v7.4.9",
        "tables": {
            name: sorted(seed.tables[name], key=lambda r: r[key])
            for name, key in TABLE_KEYS.items()
        },
    }
    if hashlib.sha256(canonical(source_snapshot).encode()).hexdigest() != knowledge.sha256:
        raise ValueError("Workbook knowledge differs from SQL knowledge")
    data = {
        t.name: deepcopy(seed.tables[t.name]) if t.schema == "knowledge" else [] for t in TABLES
    }
    qa = {t.name: [] for t in QA_TABLES}
    qa["legal_checks"] = legal_checks
    data["phien_ban_trien_khai"] = [
        native_row(
            "phien_ban_trien_khai",
            phien_ban_id=DEPLOYMENT,
            ten_phien_ban=VERSION,
            ngay_tao=RELEASE_TIME,
            legal_snapshot_sha256=knowledge.sha256,
            schema_version="v7.4.9",
            model_reasoning="AUTHORED_SYNTHETIC_PREDICATES_NO_LLM",
            prompt_version="NOT_USED",
            ghi_chu="Synthetic evaluation only; legal knowledge/source flags unchanged",
            loai_du_lieu="SYNTHETIC_EVALUATION",
        )
    ]
    runs = []
    original_profiles = {r["hop_dong_id"]: r for r in seed.tables["ho_so_hop_dong"]}
    for s in scenario_plan(seed, split):
        request, document, assessment, assertions = compile_case(
            s, knowledge, assets_dir, font_path, data
        )
        data["ca_danh_gia"].append(
            native_row(
                "ca_danh_gia",
                ca_id=s.case_id,
                hop_dong_id=s.document_id,
                moc_ap_dung=s.markers["SIGNING"],
                ngay_danh_gia=datetime.combine(
                    assessment.assessment_context.ngay_danh_gia, datetime.min.time(), timezone.utc
                ),
                trang_thai="SYNTHETIC_REFERENCE_PENDING_REVIEW",
                phien_ban_id=DEPLOYMENT,
                loai_moc_ap_dung="NGAY_GIAO_KET",
                profile_snapshot_json={
                    "mode": "SYNTHETIC_EVALUATION",
                    "scenario": s.name,
                    "profile": json.loads(canonical(s.profile)),
                    "original_seed_date": str(s.original_seed_date),
                    "real_world_verified": False,
                    "dataset_version": VERSION,
                    "human_verified": False,
                },
                loai_du_lieu="SYNTHETIC_EVALUATION",
                rule_version=request.rule_version,
                legal_knowledge_version=request.legal_knowledge_version,
                tenant_id=assessment.tenant_id,
                created_by=assessment.created_by,
            )
        )
        qa["case_manifest"].append(
            {
                "case_id": s.case_id,
                "hop_dong_id": s.document_id,
                "group_id": s.source_group,
                "split": s.split,
                "case_kind": "CORPUS",
                "label_quality": "SYNTHETIC_SPEC",
                "dataset_version": VERSION,
                "label_version": "SYNTHETIC_PREDICATES_R2",
                "knowledge_snapshot_sha256": knowledge.sha256,
                "module_scope": "C01-C13_DRAFT_SELECTED_FAMILIES",
                "limitations_json": {
                    "synthetic": True,
                    "scenario": s.name,
                    "legal_gold": False,
                    "facts_and_gates_are_test_assumptions": True,
                    "all_human_approvals_false": True,
                    "original_source_doc": s.source_doc,
                    "original_workbook_sha256": seed.source_sha256,
                    "original_seed_date": str(s.original_seed_date),
                    "text_pdf_not_scan_ocr": True,
                    "shared_archetypes_across_splits": True,
                    "checklist_complete": False,
                    "real_world_accuracy_measured": False,
                },
            }
        )
        qa["controlled_assertions"].append(
            {
                "case_id": s.case_id,
                "expected_assertions_json": assertions,
                "rationale": "Authored synthetic scenario " + s.name,
                "legal_review_id": None,
            }
        )
        qa["source_checks"].append(
            {
                "tep_id": assessment.source.tep_id,
                "hop_dong_id": s.document_id,
                "source_url": None,
                "status": "GENERATED_SYNTHETIC_PDF_AND_CANONICAL_TEXT",
                "download_sha256": assessment.source.sha256,
                "bytes": len((assets_dir / "synthetic" / (s.case_id + ".pdf")).read_bytes()),
                "error": None,
            }
        )
        qa["change_log"].append(
            {
                "change_id": s.case_id + "/SYNTHETIC_PROFILE",
                "table_name": "ho_so_hop_dong",
                "record_id": s.document_id,
                "reason": "Create separate counterfactual scenario; original input untouched",
                "before_json": json.loads(canonical(original_profiles[s.source_doc])),
                "after_json": {
                    "mode": "SYNTHETIC_EVALUATION",
                    "scenario": s.name,
                    "profile": json.loads(canonical(s.profile)),
                },
            }
        )
        runs.append((request, document, assessment, assertions))
    initial = WorkbookSeed(seed.source_sha256, data)
    validate_references(initial)
    with temporary_database(database_url) as db_url:
        seed_database(db_url, initial)
        sql_knowledge, store = Knowledge(db_url), Store(db_url)
        for request, document, assessment, assertions in runs:
            response = evaluate(request, sql_knowledge).model_copy(
                update={"produced_at": RELEASE_TIME}
            )
            assert_synthetic_response(assertions, response)
            store.save(request, response)
            context = Context(**request.model_dump(exclude={"contract_name", "payload"}))
            scopes = [
                ScopeResolution(
                    **{k: getattr(r, k) for k in ScopeResolution.model_fields if hasattr(r, k)},
                    scope_reason=r.reason["summary"],
                )
                for r in request.payload.requirements
            ]
            reasoning = ReasoningRequest(
                **context.model_dump(), payload=request.payload.model_dump(exclude={"citations"})
            )
            compliance = evaluate_compliance(reasoning, sql_knowledge)
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
            cid = request.ca_id
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
            artifact(qa, cid, "INPUT", "PipelineRequest", cid, request)
            artifact(qa, cid, "EXPECTED", "PipelineResponse", cid, response)
            artifact(qa, cid, "EXPECTED", "DocumentIntelligenceResult", cid, document)
            for name, value in (
                ("C02", document.contract_profile),
                ("C03", document.citations),
                ("C04", scopes),
                ("C05", request.payload.requirements),
                ("C06", request.payload.retrieval),
                ("C07", response.payload.criterion_results),
                ("C08", response.payload.requirement_results),
                ("C09", request.payload.citations),
                ("C10", response.payload.risks),
                ("C11", response.payload.recommendations),
                ("C13", report),
            ):
                artifact(
                    qa,
                    cid,
                    "EXPECTED",
                    name,
                    cid,
                    [r.model_dump(mode="json") for r in value]
                    if isinstance(value, list)
                    else value,
                )
            row = native_row(
                "bao_cao_danh_gia",
                bao_cao_id="SYN_R2_REPORT_" + cid,
                ca_id=cid,
                phien_ban_bao_cao=1,
                report_json={
                    "mode": "SYNTHETIC_EVALUATION",
                    "legal_gold": False,
                    "typed_c13_artifact": cid + "/EXPECTED/C13/" + cid,
                    "requirement_statuses": dict(
                        Counter(r.status for r in response.payload.requirement_results)
                    ),
                    "criterion_findings": dict(
                        Counter(r.finding for r in response.payload.criterion_results)
                    ),
                    "citation_statuses": [c.status for c in request.payload.citations],
                    "risk_count": len(response.payload.risks),
                    "recommendation_count": len(response.payload.recommendations),
                },
                so_yeu_cau_ung_vien=len(request.payload.requirements),
                so_yeu_cau_da_phan_giai=sum(r.confirmed for r in request.payload.requirements),
                so_yeu_cau_da_danh_gia=len(response.payload.requirement_results),
                mau_so_score=sum(r.mandatory for r in response.payload.criterion_results),
                score_method="NO_OVERALL_SCORE_SELECTED_CHECKLIST_ONLY",
                model_version="AUTHORED_SYNTHETIC_PREDICATES_NO_LLM",
                prompt_version="NOT_USED",
                ngay_tao=RELEASE_TIME,
                loai_du_lieu="SYNTHETIC_EVALUATION",
                report_status="DRAFT",
                review_status="PENDING",
                so_unknown=sum(r.finding == "UNKNOWN" for r in response.payload.criterion_results),
                knowledge_snapshot_sha256=knowledge.sha256,
                rule_version=request.rule_version,
            )
            with connect_postgres(db_url) as connection:
                insert(
                    connection, "runtime", "bao_cao_danh_gia", "bao_cao_id", row, ("report_json",)
                )
            print("Built synthetic reference", cid, flush=True)
        with connect_postgres(db_url) as connection:
            # Exercise SQL CHECK/FK/immutability constraints on the complete QA payload too.
            for table in QA_TABLES:
                insert_table(connection, table, qa[table.name])
            connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
            data = {
                t.name: connection.execute(
                    sql.SQL("SELECT * FROM {} ORDER BY {}").format(
                        sql.Identifier(t.schema, t.name), sql.Identifier(t.primary_key)
                    )
                ).fetchall()
                for t in TABLES
            }
    for name in OUTPUT_TABLES:
        for row in data[name]:
            row["loai_du_lieu"] = "SYNTHETIC_EVALUATION"
    release = WorkbookSeed(seed.source_sha256, data, qa)
    validate_references(release)
    validate_qa(release)
    return release


def distribution_rows(seed):
    splits = {r["case_id"]: r["split"] for r in seed.qa_tables["case_manifest"]}
    req_cases = {r["yeu_cau_ca_id"]: r["ca_id"] for r in seed.tables["yeu_cau_ap_dung"]}
    counts = Counter()
    for table, field in (
        ("yeu_cau_ap_dung", "applicability_status"),
        ("ket_qua_tieu_chi", "loai_phat_hien"),
        ("ket_qua_tuan_thu", "nhan"),
        ("phat_hien_vien_dan", "trang_thai"),
        ("ket_qua_rui_ro", "loai_rui_ro"),
    ):
        for row in seed.tables[table]:
            cid = row.get("ca_id") or req_cases[row["yeu_cau_ca_id"]]
            for split in (splits[cid], "ALL"):
                counts[(table, split, row[field])] += 1
    for row in seed.tables["yeu_cau_ap_dung"]:
        for field in ("scope_status", "version_status"):
            for part in (splits[row["ca_id"]], "ALL"):
                counts[("C05_" + field, part, row[field])] += 1
    for row in seed.qa_tables["case_manifest"]:
        scenario = row["limitations_json"].get("scenario")
        if scenario:
            for split in (row["split"], "ALL"):
                counts[("SCENARIO", split, scenario)] += 1
    outcomes = {}
    priority = {"COMPLIANT": 0, "PARTIAL": 1, "INSUFFICIENT": 2, "NON_COMPLIANT": 3}
    for row in seed.tables["ket_qua_tuan_thu"]:
        cid = req_cases[row["yeu_cau_ca_id"]]
        current = outcomes.get(cid, "COMPLIANT")
        outcomes[cid] = max((current, row["nhan"]), key=priority.get)
    for cid, split in splits.items():
        if seed.tables["yeu_cau_ap_dung"]:
            for part in (split, "ALL"):
                counts[
                    ("SELECTED_CHECKLIST_BRANCH", part, outcomes.get(cid, "NOT_APPLICABLE"))
                ] += 1
    return [[*key, value] for key, value in sorted(counts.items())]
