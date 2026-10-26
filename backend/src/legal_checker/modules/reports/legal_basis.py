"""Describe the legal-basis IDs a report cites, from the knowledge snapshot it pinned.

Reports store IDs only (legal documents, articles, requirement versions). Display names,
numbers, effective ranges and verification flags are read from the exact snapshot recorded
in audit.context, never from whatever knowledge is current.
"""

from typing import Any

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.report import FinalReport


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
            "url": document.get("url_nguon"),
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
            "url": article.get("url_nguon"),
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
