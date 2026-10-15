"""C01: intake produces a pinned assessment and an accessible source reference."""

from datetime import date

from pydantic import Field, model_validator

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


class AssessmentCase(Model):
    ca_id: str
    hop_dong_id: str
    source: SourceDocument
    assessment_context: AssessmentTiming
    deployment: DeploymentPin
    tenant_id: str
    created_by: str
