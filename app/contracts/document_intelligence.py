from pydantic import ConfigDict, Field, model_validator

from app.contracts.common import Model


class Chunk(Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    doan_id: str = Field(min_length=1)
    hop_dong_id: str = Field(min_length=1)
    noi_dung: str = Field(min_length=1)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)

    @model_validator(mode="after")
    def page_range(self):
        if self.page_end < self.page_start:
            raise ValueError("Invalid page range")
        return self


class Evidence(Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    doan_id: str
    trich_dan: str = Field(min_length=1)
    ky_tu_bat_dau: int = Field(ge=0)
    ky_tu_ket_thuc: int = Field(ge=1)

    @model_validator(mode="after")
    def offsets(self):
        if self.ky_tu_ket_thuc <= self.ky_tu_bat_dau:
            raise ValueError("Evidence offsets must define a nonempty interval")
        return self


class ExternalEvidence(Model):
    bang_chung_id: str
    object_uri: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    verified: bool = False


class ExtractedFact(Model):
    trich_xuat_id: str
    ten_truong: str
    gia_tri_raw: str | None = None
    gia_tri_chuan_json: object | None = None
    trang_thai: str
    phuong_phap: str
    human_verified: bool = False
    evidence_ids: list[str] = Field(default_factory=list)


class ContractProfile(Model):
    """C02 starter: preserve uncertain profile fields and provenance supplied by extraction."""

    hop_dong_id: str
    profile: dict[str, object | None]
    subjects: list[dict[str, object]] = Field(default_factory=list)
    time_markers: list[dict[str, object]] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)
