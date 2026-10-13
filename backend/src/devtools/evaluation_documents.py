"""Literal extraction specifications with actual synthetic PDF bytes, not legal opinions."""

import hashlib

from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import DocumentIntelligenceResult
from legal_checker.shared.contracts.handoffs import DocumentInput


def ascii_pdf(lines):
    """Single-page, text-bearing PDF; deliberately simple to isolate extraction behavior."""
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    stream = (
        "BT /F1 11 Tf 14 TL 50 740 Td "
        + " Tj T* ".join("(" + line + ")" for line in escaped)
        + " Tj ET"
    ).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n"
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    out += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"
    return out


def document_specifications(knowledge, assets_dir):
    rows = []
    variants = [
        (
            "KNOWN_DATE_AND_CITATION",
            ["Signing date: 2024-09-01.", "Legal citation: 29/2023/QH15."],
            "2024-09-01",
            "EXTRACTED",
            True,
        ),
        ("PLACEHOLDER_DATE", ["Signing date: ..../..../...."], "", "PLACEHOLDER", False),
        ("MISSING_DATE", [], None, "UNKNOWN", False),
        (
            "CONFLICTING_DATE",
            ["Signing date: 2024-09-01.", "Signing date: 2024-10-01."],
            None,
            "CONFLICT",
            False,
        ),
        (
            "AMBIGUOUS_DATE",
            ["Signing date: 01/02/2024 (date format unspecified)."],
            None,
            "AMBIGUOUS",
            False,
        ),
        ("NO_CITATION", ["Signing date: 2024-09-01."], "2024-09-01", "EXTRACTED", False),
        ("UNKNOWN_BOOLEAN", ["Foreign seller: UNKNOWN."], None, "UNKNOWN", False),
        (
            "CONFLICTING_BOOLEAN",
            ["Foreign seller: Yes.", "Foreign seller: No."],
            None,
            "UNKNOWN",
            False,
        ),
    ]
    for name, extra, day, status, has_citation in variants:
        cid = "QA_DOC_" + name
        doc = cid + "_DOC"
        chunk = cid + "_CHUNK"
        lines = [
            "SYNTHETIC TEST FIXTURE - NOT A REAL TRANSACTION",
            "Seller: Company A.",
            "Buyer: Buyer B.",
            *extra,
        ]
        text = "\n".join(lines)
        raw = ascii_pdf(lines)
        (assets_dir / "controlled").mkdir(parents=True, exist_ok=True)
        (assets_dir / "controlled" / (cid + ".pdf")).write_bytes(raw)
        (assets_dir / "controlled" / (cid + ".txt")).write_text(text)
        context = Context(
            ca_id=cid,
            phien_ban_id="QA_SYNTHETIC_V750_R1",
            rule_version="CAN_HO_SEED_RULES_20261007",
            legal_knowledge_version="V749_LEGAL_KNOWLEDGE_PENDING_HUMAN",
            knowledge_snapshot_sha256=knowledge.sha256,
            run_id=cid + "_RUN",
            trace_id=cid + "_TRACE",
        )
        case = AssessmentCase(
            ca_id=cid,
            hop_dong_id=doc,
            source={
                "tep_id": cid + "_SOURCE",
                "object_uri": "dataset://v750-r1/sources/controlled/" + cid + ".pdf",
                "mime_type": "application/pdf",
                "sha256": hashlib.sha256(raw).hexdigest(),
            },
            assessment_context={"ngay_danh_gia": "2024-09-01"},
            deployment={
                "phien_ban_id": context.phien_ban_id,
                "rule_version": context.rule_version,
                "legal_knowledge_version": context.legal_knowledge_version,
            },
            tenant_id="QA_SYNTHETIC",
            created_by="SPEC_AUTHOR",
        )
        evidence = []
        facts = []
        subjects = []
        for field, value, role in [
            ("ten_chu_the", "Company A", "BEN_BAN"),
            ("ten_chu_the", "Buyer B", "BEN_MUA"),
        ]:
            eid = cid + "_" + role + "_E"
            start = text.index(value)
            evidence.append(
                {
                    "bang_chung_id": eid,
                    "doan_id": chunk,
                    "trich_dan": value,
                    "ky_tu_bat_dau": start,
                    "ky_tu_ket_thuc": start + len(value),
                }
            )
            facts.append(
                {
                    "trich_xuat_id": cid + "_" + role + "_FACT",
                    "ten_truong": field,
                    "gia_tri_raw": value,
                    "gia_tri_chuan_json": value,
                    "trang_thai": "EXTRACTED",
                    "phuong_phap": "LITERAL_SYNTHETIC_SPEC",
                    "evidence_ids": [eid],
                }
            )
            subjects.append({"chu_the_id": cid + "_" + role, "vai_tro": role, "ten_chu_the": value})
        citations = []
        markers = []
        date_raw = " | ".join(line for line in extra if line.startswith("Signing date:")) or None
        date_fact_id = cid + "_DATE_FACT"
        date_evidence_ids = []
        if day:
            date_eid = cid + "_DATE_E"
            start = text.index(day)
            evidence.append(
                {
                    "bang_chung_id": date_eid,
                    "doan_id": chunk,
                    "trich_dan": day,
                    "ky_tu_bat_dau": start,
                    "ky_tu_ket_thuc": start + len(day),
                }
            )
            date_evidence_ids.append(date_eid)
        facts.append(
            {
                "trich_xuat_id": date_fact_id,
                "ten_truong": "ngay_giao_ket",
                "gia_tri_raw": date_raw,
                "gia_tri_chuan_json": day or None,
                "trang_thai": status,
                "phuong_phap": "LITERAL_SYNTHETIC_SPEC",
                "evidence_ids": date_evidence_ids,
            }
        )
        markers.append(
            {
                "moc_id": cid + "_SIGNING",
                "loai_moc": "NGAY_GIAO_KET",
                "gia_tri_raw": date_raw,
                "ngay": day or None,
                "trang_thai": status,
                "duoc_dung_phan_giai": False,
                "trich_xuat_id": date_fact_id,
            }
        )
        if has_citation:
            citations = [
                {
                    "vien_dan_id": cid + "_CIT",
                    "hop_dong_id": doc,
                    "raw_text": "29/2023/QH15",
                    "normalized": {"so_hieu": "29/2023/QH15", "nam": 2023},
                    "extraction": {"status": "EXTRACTED"},
                    "evidence": [{"doan_id": chunk, "page_start": 1, "page_end": 1}],
                }
            ]
        output = DocumentIntelligenceResult(
            contract_profile={
                "hop_dong_id": doc,
                "profile": {
                    "ngay_giao_ket": day or None,
                    "trang_thai_ngay": status,
                    "ngay_giao_ket_raw": " | ".join(extra) if extra else None,
                    "ben_ban_co_von_nuoc_ngoai": None,
                },
                "subjects": subjects,
                "time_markers": markers,
                "facts": facts,
                "evidence": evidence,
            },
            chunks=[
                {
                    "doan_id": chunk,
                    "hop_dong_id": doc,
                    "noi_dung": text,
                    "page_start": 1,
                    "page_end": 1,
                }
            ],
            citations=citations,
        )
        rows.append(
            {
                "case_id": cid,
                "input": DocumentInput(context=context, case=case),
                "output": output,
                "assertions": {
                    "module": "documents",
                    "ngay_giao_ket": day or None,
                    "trang_thai_ngay": status,
                    "citation_count": len(citations),
                    "foreign_seller": None,
                    "seller_name": "Company A",
                    "buyer_name": "Buyer B",
                    "chunk_ids_are_reference_only": True,
                    "text_normalization": "ASCII lines joined with LF; trim terminal separators",
                },
                "rationale": name,
            }
        )
    return rows
