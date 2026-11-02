"""C09 classification from identity, temporal and domain results."""

from dataclasses import dataclass
from typing import Literal

from legal_checker.modules.citation_validation.identity_validator import IdentityResult
from legal_checker.modules.citation_validation.temporal_validator import TemporalResult

CitationStatus = Literal["VALID", "STALE", "INVALID", "UNKNOWN"]

_LY_DO = {
    "NAME_ONLY_VERSION_IDENTITY_AMBIGUOUS": "Viện dẫn chỉ có tên văn bản, không có số hiệu/năm; "
    "không đủ để xác định văn bản và phiên bản.",
    "NUMBER_NOT_IN_CATALOG": "Số hiệu không có trong danh mục văn bản đã thu thập; chưa xác minh "
    "được, không kết luận là sai.",
    "MULTIPLE_CATALOG_CANDIDATES": "Số hiệu khớp nhiều văn bản trong danh mục; chưa chọn được.",
    "NUMBER_TITLE_MISMATCH": "Số hiệu thuộc một văn bản khác với tên văn bản được viện dẫn.",
    "RELEVANT_DATE_UNKNOWN": "Không xác định được ngày giao kết để xét hiệu lực.",
    "EFFECTIVE_DATE_UNKNOWN": "Danh mục chưa có ngày hiệu lực của văn bản.",
    "NOT_YET_IN_FORCE_AT_DATE": "Văn bản chưa có hiệu lực tại ngày giao kết.",
    "REPLACED_BEFORE_DATE": "Văn bản đã bị thay thế trước ngày giao kết.",
    "EXPIRED_BEFORE_DATE": "Văn bản đã hết hiệu lực trước ngày giao kết.",
    "DOMAIN_MISMATCH": "Văn bản thuộc lĩnh vực không phù hợp với hợp đồng.",
    "IN_FORCE_AT_DATE": "Văn bản có hiệu lực tại ngày giao kết và phù hợp lĩnh vực.",
}


@dataclass
class Classification:
    status: CitationStatus
    reason_code: str
    ly_do: str


def classify(
    identity: IdentityResult, temporal: TemporalResult | None, domain_status: str
) -> Classification:
    """Order: identity, then validity at the relevant date, then domain.

    UNKNOWN is never upgraded by later checks; only proven facts yield INVALID/STALE.
    """
    if identity.status == "UNKNOWN":
        code = identity.reason_code
        return Classification("UNKNOWN", code, _LY_DO[code])
    if identity.status == "MISMATCH":
        code = identity.reason_code
        return Classification("INVALID", code, f"{_LY_DO[code]} ({identity.detail})")
    assert temporal is not None
    code = temporal.reason_code
    if temporal.status == "UNKNOWN":
        return Classification("UNKNOWN", code, _LY_DO[code])
    if temporal.status == "NOT_YET_IN_FORCE":
        return Classification("INVALID", code, f"{_LY_DO[code]} ({temporal.detail})")
    if temporal.status == "STALE":
        return Classification("STALE", code, f"{_LY_DO[code]} ({temporal.detail})")
    if domain_status == "MISMATCH":
        return Classification("INVALID", "DOMAIN_MISMATCH", _LY_DO["DOMAIN_MISMATCH"])
    return Classification("VALID", code, _LY_DO[code])
