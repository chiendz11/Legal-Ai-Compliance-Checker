from datetime import date
from typing import Any, Literal

from pydantic import Field, model_validator

from legal_checker.shared.contracts.common import Model


class CitationValidation(Model):
    finding_id: str
    ca_id: str
    vien_dan_id: str
    normalized_van_ban_id: str | None = None
    relevant_date: date | None = None
    status: Literal["VALID", "STALE", "INVALID", "UNKNOWN"]
    reason_code: str
    ly_do: str
    domain_status: Literal["MATCH", "MISMATCH", "UNKNOWN"]
    finding_verified: bool
    current_status: str | None = None
    replacement_van_ban_id: str | None = None
    source_snapshot_json: dict[str, Any]
    lan_chay_id: str
    knowledge_version: str


class CitationNormalization(Model):
    so_hieu: str | None = None
    ten_van_ban: str | None = None
    loai_van_ban: str | None = None
    nam: int | None = None
    ngay_ban_hanh: date | None = None
    dieu: str | None = None
    khoan: str | None = None


class CitationExtractionMetadata(Model):
    status: Literal["EXTRACTED", "AMBIGUOUS", "UNKNOWN"]
    confidence: float | None = Field(default=None, ge=0, le=1)


class CitationPosition(Model):
    doan_id: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)

    @model_validator(mode="after")
    def page_range(self):
        if self.page_end < self.page_start:
            raise ValueError("Invalid citation page range")
        return self


class CitationExtraction(Model):
    """C03: contract-authored citations; independent of the applicable-law checklist."""

    vien_dan_id: str
    hop_dong_id: str
    raw_text: str
    normalized: CitationNormalization
    extraction: CitationExtractionMetadata
    evidence: list[CitationPosition] = Field(min_length=1)
