"""Resolve citation identity without silently choosing a law version by today's date."""

from dataclasses import dataclass, field
from typing import Any, Literal

from legal_checker.modules.citation_validation.normalizer import (
    fold,
    number_key,
    number_year,
    title_core,
)
from legal_checker.shared.contracts.citation import CitationExtraction

IDENTITY_POLICY = "C09_CATALOG_IDENTITY_V2"
# Exact, reviewable aliases; no fuzzy subset matching for name-only identity.
TITLE_ALIASES = {
    "luat bao ve nguoi tieu dung": "luat bao ve quyen loi nguoi tieu dung",
}
IdentityStatus = Literal["MATCHED", "MISMATCH", "UNKNOWN"]


@dataclass
class IdentityResult:
    status: IdentityStatus
    reason_code: str
    document: dict[str, Any] | None = None
    candidates: list[str] = field(default_factory=list)
    detail: str = ""
    anchor_citation_ids: list[str] = field(default_factory=list)


def canonical_title(title):
    key = fold(title or "")
    return TITLE_ALIASES.get(key, key)


def _titles_conflict(cited: str | None, catalog: str | None) -> bool:
    if not cited or not catalog:
        return False
    if not fold(cited).startswith(("luat", "bo luat")) or not fold(catalog).startswith(
        ("luat", "bo luat")
    ):
        return False
    a, b = title_core(cited), title_core(catalog)
    if not a or not b:
        return False
    words_a, words_b = set(a.split()), set(b.split())
    return not (words_a <= words_b or words_b <= words_a)


def numbered_anchors(citations, documents):
    """Only explicit, source-extracted numbers with verified catalog identity anchor references."""
    anchors = {}
    for citation in citations:
        if citation.normalized.so_hieu is None or citation.extraction.status != "EXTRACTED":
            continue
        result = validate_identity(citation, documents)
        if result.status != "MATCHED" or result.document.get("identity_verified") is not True:
            continue
        title = canonical_title(result.document.get("ten_van_ban"))
        anchors.setdefault(title, []).append((result.document["van_ban_id"], citation.vien_dan_id))
    return anchors


def validate_identity(
    citation: CitationExtraction, documents: dict[str, dict[str, Any]], *, anchors=None
) -> IdentityResult:
    """Number, unique exact title+year, or a unique explicit reference in this contract.

    A bare name does not select the active/latest catalog version. Ambiguous candidates,
    conflicting anchors, unsupported aliases and dynamic references remain UNKNOWN.
    """
    normalized = citation.normalized
    key = number_key(normalized.so_hieu)
    if key is None:
        title = canonical_title(normalized.ten_van_ban)
        candidates = sorted(
            doc_id
            for doc_id, doc in documents.items()
            if title and title == canonical_title(doc.get("ten_van_ban"))
        )
        if normalized.nam is not None:
            by_year = [
                doc_id
                for doc_id in candidates
                if number_year(
                    documents[doc_id].get("so_hieu_chuan") or documents[doc_id].get("so_hieu")
                )
                == normalized.nam
            ]
            if len(by_year) == 1:
                document = documents[by_year[0]]
                return IdentityResult(
                    "MATCHED",
                    "CATALOG_TITLE_YEAR_MATCH",
                    document,
                    by_year,
                    f"exact catalog title and promulgation year {normalized.nam}",
                )
            return IdentityResult(
                "UNKNOWN",
                "TITLE_YEAR_IDENTITY_UNRESOLVED",
                candidates=by_year or candidates,
                detail="title/year has no unique catalog identity",
            )
        linked = (anchors or {}).get(title, [])
        ids = sorted({doc_id for doc_id, _ in linked})
        dynamic = any(term in fold(citation.raw_text) for term in ("hien hanh", "tung thoi diem"))
        if len(ids) == 1 and not dynamic:
            return IdentityResult(
                "MATCHED",
                "CONTRACT_NUMBER_ANCHOR_MATCH",
                documents[ids[0]],
                ids,
                "unqualified same-title reference resolves to a unique explicit number "
                "in this contract",
                sorted({cid for _, cid in linked}),
            )
        return IdentityResult(
            "UNKNOWN",
            "NAME_ONLY_VERSION_IDENTITY_AMBIGUOUS",
            candidates=candidates,
            detail="no unique static number anchor; a bare law name does not identify the version",
        )
    matches = [
        doc
        for doc in documents.values()
        if key in {number_key(doc.get("so_hieu_chuan")), number_key(doc.get("so_hieu"))}
    ]
    if not matches:
        return IdentityResult(
            "UNKNOWN", "NUMBER_NOT_IN_CATALOG", detail=f"{normalized.so_hieu} not in catalog"
        )
    if len(matches) > 1:
        return IdentityResult(
            "UNKNOWN",
            "MULTIPLE_CATALOG_CANDIDATES",
            candidates=sorted(d["van_ban_id"] for d in matches),
            detail=f"{len(matches)} catalog documents share {normalized.so_hieu}",
        )
    document = matches[0]
    if _titles_conflict(normalized.ten_van_ban, document.get("ten_van_ban")):
        return IdentityResult(
            "MISMATCH",
            "NUMBER_TITLE_MISMATCH",
            document,
            [document["van_ban_id"]],
            f"'{normalized.ten_van_ban}' cited with number of '{document['ten_van_ban']}'",
        )
    if normalized.nam is not None and normalized.nam != number_year(normalized.so_hieu):
        return IdentityResult(
            "MISMATCH",
            "NUMBER_YEAR_MISMATCH",
            document,
            [document["van_ban_id"]],
            "observed year conflicts with the explicitly cited number",
        )
    return IdentityResult(
        "MATCHED", "CATALOG_NUMBER_MATCH", document, [document["van_ban_id"]], "number match"
    )
