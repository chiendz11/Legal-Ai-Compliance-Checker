"""Legal document identity: which catalog document (if any) a citation names."""

from dataclasses import dataclass, field
from typing import Any, Literal

from legal_checker.modules.citation_validation.normalizer import fold, number_key, title_core
from legal_checker.shared.contracts.citation import CitationExtraction

IdentityStatus = Literal["MATCHED", "MISMATCH", "UNKNOWN"]


@dataclass
class IdentityResult:
    status: IdentityStatus
    reason_code: str
    document: dict[str, Any] | None = None
    candidates: list[str] = field(default_factory=list)
    detail: str = ""


def _titles_conflict(cited: str | None, catalog: str | None) -> bool:
    """Only law names are compared ('Luật X' vs 'Luật Y'); decrees/circulars have long
    descriptive catalog titles, so a short citation title proves nothing about them."""
    if not cited or not catalog:
        return False
    if not fold(cited).startswith(("luat", "bo luat")) or not fold(catalog).startswith(
        ("luat", "bo luat")
    ):
        return False
    a, b = title_core(cited), title_core(catalog)
    if not a or not b:
        return False
    # Short forms drop words ("Bảo vệ người tiêu dùng" for "Bảo vệ quyền lợi người tiêu
    # dùng"); a conflict needs words the other title does not contain on both sides.
    words_a, words_b = set(a.split()), set(b.split())
    return not (words_a <= words_b or words_b <= words_a)


def validate_identity(
    citation: CitationExtraction, documents: dict[str, dict[str, Any]]
) -> IdentityResult:
    """A number is required: a name without number/year cannot select a version (rule 1).
    A number absent from the catalog is UNKNOWN, never INVALID; the catalog is partial."""
    normalized = citation.normalized
    key = number_key(normalized.so_hieu)
    if key is None:
        title = normalized.ten_van_ban
        candidates = sorted(
            doc_id
            for doc_id, doc in documents.items()
            if title
            and doc.get("ten_van_ban")
            and title_core(title) == title_core(doc["ten_van_ban"])
        )
        return IdentityResult(
            "UNKNOWN",
            "NAME_ONLY_VERSION_IDENTITY_AMBIGUOUS",
            candidates=candidates,
            detail="no document number; a law name alone does not identify the version",
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
    return IdentityResult(
        "MATCHED", "CATALOG_NUMBER_MATCH", document, [document["van_ban_id"]], "number match"
    )
