from datetime import date
from decimal import Decimal

from pydantic import ConfigDict, Field, model_validator

from legal_checker.shared.contracts.citation import CitationExtraction
from legal_checker.shared.contracts.common import Model


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


class ProfileFields(Model):
    """C02 fields from the data contract. Unknown values remain null, including booleans."""

    loai_hop_dong_id: str | None = None
    doi_tuong: str | None = None
    linh_vuc: str | None = None
    he_phap_luat: str | None = None
    muc_dich_giao_dich: str | None = None
    ngay_giao_ket: date | None = None
    ngay_giao_ket_raw: str | None = None
    do_chinh_xac_ngay: str | None = None
    trang_thai_ngay: str | None = None
    loai_moc_ap_dung: str | None = None
    ngay_hieu_luc_hop_dong: date | None = None
    ngay_ban_giao_du_kien: date | None = None
    quan_he_chu_the: str | None = None
    ben_ban_co_von_nuoc_ngoai: bool | None = Field(default=None, strict=True)
    ben_ban_la_chu_dau_tu: bool | None = Field(default=None, strict=True)
    ben_ban_la_ca_nhan: bool | None = Field(default=None, strict=True)
    ben_mua_la_ca_nhan: bool | None = Field(default=None, strict=True)
    gia_tri_hop_dong: Decimal | None = None
    don_vi_tien: str | None = None
    tinh_trang_tai_san: str | None = None
    la_nha_o_xa_hoi: bool | None = Field(default=None, strict=True)
    la_hop_dong_theo_mau: bool | None = Field(default=None, strict=True)
    la_nha_xay_moi: bool | None = Field(default=None, strict=True)
    che_do_giao_dich: str | None = None
    muc_dich_su_dung_can_ho: str | None = None


class ProfileSubject(Model):
    chu_the_id: str
    vai_tro: str
    ten_chu_the: str | None = None
    loai_chu_the: str | None = None
    la_thuong_nhan: bool | None = Field(default=None, strict=True)
    la_chu_the_kinh_doanh: bool | None = Field(default=None, strict=True)
    human_verified: bool = False
    doan_bang_chung_id: str | None = None


class ProfileTimeMarker(Model):
    moc_id: str
    loai_moc: str
    gia_tri_raw: str | None = None
    ngay: date | None = None
    do_chinh_xac: str | None = None
    trang_thai: str
    duoc_dung_phan_giai: bool = False
    trich_xuat_id: str | None = None


class ProfileEvidence(Evidence):
    bang_chung_id: str


class ContractProfile(Model):
    """C02: typed extraction output with nullable facts and explicit provenance."""

    hop_dong_id: str
    profile: ProfileFields
    subjects: list[ProfileSubject] = Field(default_factory=list)
    time_markers: list[ProfileTimeMarker] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)
    evidence: list[ProfileEvidence] = Field(default_factory=list)


class DocumentIntelligenceResult(Model):
    contract_profile: ContractProfile
    chunks: list[Chunk]
    citations: list[CitationExtraction]
