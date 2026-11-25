"""Describe the legal-basis IDs a report cites, from the knowledge snapshot it pinned.

Reports store IDs only (legal documents, articles, requirement versions). Display names,
numbers, effective ranges and verification flags are read from the exact snapshot recorded
in audit.context, never from whatever knowledge is current.
"""

import re
from typing import Any

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.report import FinalReport

# vbpl.vn moved to a new site: the old document pages (".../Pages/vbpq-thuoctinh.aspx?ItemID=N"
# and "vbpq-toanvan.aspx") now land on the home page, while "/van-ban/chi-tiet/van-ban--N"
# opens the same document by the same ItemID (checked for every document in the catalogue).
# "Related documents" pages point at another document, so they are left for the data owner.
_OLD_VBPL = re.compile(
    r"^https?://(?:www\.)?vbpl\.vn/.+/Pages/vbpq-(?:thuoctinh|toanvan)\.aspx\?(?:.*&)?ItemID=(\d+)",
    re.IGNORECASE,
)


def live_source_url(url: str | None) -> str | None:
    """The stored source link, rewritten when it uses vbpl.vn's retired address format."""
    if not url:
        return url
    match = _OLD_VBPL.match(url)
    return f"https://vbpl.vn/van-ban/chi-tiet/van-ban--{match.group(1)}" if match else url


def cited_ids(report: FinalReport) -> list[str]:
    content = report.report_json
    ids: set[str] = set()
    for criterion in content.compliance.criterion_results:
        ids.update(criterion.legal_basis_ids)
    for item in content.compliance.legal_basis:
        if isinstance(item.get("id"), str):
            ids.add(item["id"])
    for risk in (*content.risks.compliance, *content.risks.citation, *content.risks.verification):
        ids.update(risk.legal_basis_ids)
    for recommendation in content.recommendations:
        ids.update(recommendation.legal_basis_ids)
    for requirement in content.applicable_legal_scope:
        if requirement.requirement_version_id:
            ids.add(requirement.requirement_version_id)
    # Each requirement result names its source document and article; screens show them as the
    # requirement's legal basis, so they need display names too ("version" in reference runs,
    # "requirement_version" in module runs).
    for result in content.compliance.requirement_results:
        snapshot = result.requirement_snapshot_json or {}
        version = snapshot.get("version") or snapshot.get("requirement_version") or {}
        if isinstance(version, dict):
            ids.update(
                v for v in (version.get("source_van_ban_id"), version.get("dieu_khoan_id")) if v
            )
    for finding in content.citation_validation.findings:
        ids.update(i for i in (finding.normalized_van_ban_id, finding.replacement_van_ban_id) if i)
    return sorted(ids)


def _document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None
    return {
        "van_ban_id": document["van_ban_id"],
        "so_hieu": document.get("so_hieu"),
        "ten_van_ban": document.get("ten_van_ban"),
    }


def describe(knowledge: KnowledgeSnapshot, legal_id: str) -> dict[str, Any]:
    """One display record; unknown IDs stay visible as UNKNOWN instead of being dropped."""
    if document := knowledge.documents.get(legal_id):
        return {
            "id": legal_id,
            "kind": "DOCUMENT",
            "title": document.get("ten_van_ban") or legal_id,
            "number": document.get("so_hieu"),
            "effective_from": document.get("hieu_luc_tu"),
            "effective_to": document.get("hieu_luc_den"),
            "status": document.get("trang_thai"),
            "url": live_source_url(document.get("url_nguon")),
            "verification": document.get("trang_thai_xac_minh"),
            "document": _document(document),
        }
    if article := knowledge.articles.get(legal_id):
        document_id = article.get("van_ban_id") or article.get("source_van_ban_id")
        text = article.get("noi_dung_nguon") or article.get("noi_dung") or ""
        return {
            "id": legal_id,
            "kind": "ARTICLE",
            "title": article.get("vi_tri") or text[:80] or legal_id,
            "excerpt": text[:400],
            "effective_from": article.get("hieu_luc_tu"),
            "effective_to": article.get("hieu_luc_den"),
            "pages": [article.get("page_start"), article.get("page_end")],
            "url": live_source_url(article.get("url_nguon")),
            "verification": article.get("trang_thai_xac_minh") or article.get("loai_du_lieu"),
            "document": _document(knowledge.documents.get(document_id)),
        }
    if version := knowledge.versions.get(legal_id):
        return {
            "id": legal_id,
            "kind": "REQUIREMENT_VERSION",
            "title": version.get("noi_dung") or legal_id,
            "requirement_id": version.get("requirement_id"),
            "effective_from": version.get("hieu_luc_tu"),
            "effective_to": version.get("hieu_luc_den"),
            "article_id": version.get("dieu_khoan_id"),
            "verification": version.get("trang_thai_ra_soat"),
            "document": _document(knowledge.documents.get(version.get("source_van_ban_id"))),
        }
    return {"id": legal_id, "kind": "UNKNOWN", "title": legal_id}


def legal_basis_for(report: FinalReport, knowledge: KnowledgeSnapshot) -> list[dict[str, Any]]:
    pinned = report.report_json.audit.get("context", {}).get("knowledge_snapshot_sha256")
    if pinned != knowledge.sha256:
        raise ValueError("Knowledge snapshot differs from the one the report pinned")
    return [describe(knowledge, legal_id) for legal_id in cited_ids(report)]


def requirement_names_for(
    report: FinalReport, knowledge: KnowledgeSnapshot
) -> list[dict[str, Any]]:
    """Plain-language names of every requirement the report lists (checklist and scope).

    Requirements without a resolved version have no version text to show, so screens fell
    back to codes such as FAM_APT_DEPOSIT. The requirement row of the pinned snapshot names
    each one; an ID missing from the snapshot keeps its code as the title.
    """
    pinned = report.report_json.audit.get("context", {}).get("knowledge_snapshot_sha256")
    if pinned != knowledge.sha256:
        raise ValueError("Knowledge snapshot differs from the one the report pinned")
    content = report.report_json
    ids = sorted(
        {a.requirement_id for a in content.applicable_legal_scope if a.requirement_id}
        | {c.requirement_id for c in content.checklist if c.requirement_id}
    )
    rows = {r["requirement_id"]: r for r in knowledge.tables.get("yeu_cau_phap_ly", [])}
    return [
        {
            "requirement_id": requirement_id,
            "title": (rows.get(requirement_id) or {}).get("ten_nhom_yeu_cau") or requirement_id,
            "obligation_group": (rows.get(requirement_id) or {}).get("nhom_nghia_vu"),
        }
        for requirement_id in ids
    ]
