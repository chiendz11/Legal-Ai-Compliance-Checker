"""C01: intake produces a pinned assessment and an accessible source reference."""

from datetime import date
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from legal_checker.shared.contracts.common import DeploymentPin, Model


class SourceDocument(Model):
    tep_id: str = Field(min_length=1)
    url_nguon: str | None = None
    object_uri: str | None = None
    mime_type: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def source_reference(self):
        if not self.object_uri and not self.url_nguon:
            raise ValueError("A source document needs an object URI or source URL")
        return self


class AssessmentTiming(Model):
    ngay_danh_gia: date
    moc_ap_dung: date | None = None
    loai_moc_ap_dung: str | None = None
    review_mode: Literal["FULL_ASSESSMENT", "DRAFT_REVIEW"] = "FULL_ASSESSMENT"
    # Receipt of the contract/annex set, not human approval or proof of execution.
    document_set_complete: bool = False

    @model_serializer(mode="wrap")
    def preserve_legacy_report_bytes(self, handler):
        data = handler(self)
        # Frozen reports predating these fields must keep their original digest.
        # New database/API cases explicitly set both values and persist them.
        for name in ("review_mode", "document_set_complete"):
            if name not in self.model_fields_set:
                data.pop(name, None)
        return data


class AssessmentCase(Model):
    ca_id: str
    hop_dong_id: str
    source: SourceDocument
    assessment_context: AssessmentTiming
    deployment: DeploymentPin
    tenant_id: str
    created_by: str
