"""X02: metadata for actual LLM calls; unknown usage/cost remains null."""

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from legal_checker.shared.contracts.common import Model


class LlmAudit(Model):
    lan_goi_id: str = Field(min_length=1)
    ca_id: str = Field(min_length=1)
    module: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    input_tokens: int | None = Field(default=None, ge=0, strict=True)
    output_tokens: int | None = Field(default=None, ge=0, strict=True)
    latency_ms: int = Field(ge=0, strict=True)
    chi_phi: Decimal | None = Field(default=None, ge=0)
    don_vi_tien: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    trang_thai: Literal["SUCCESS", "ERROR"]
    ma_loi: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{0,63}$")
    so_lan_thu: int = Field(ge=1, strict=True)
    trace_id: str = Field(min_length=1)
    ngay_goi: AwareDatetime

    @model_validator(mode="after")
    def consistent_outcome(self):
        if self.trang_thai == "SUCCESS" and (not self.output_sha256 or self.ma_loi):
            raise ValueError("SUCCESS needs an output hash and no error code")
        if self.trang_thai == "ERROR" and not self.ma_loi:
            raise ValueError("ERROR needs a non-sensitive error code")
        if self.chi_phi is not None and not self.don_vi_tien:
            raise ValueError("A reported cost needs a currency")
        return self
