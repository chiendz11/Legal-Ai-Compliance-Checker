"""X02: real provider-call audit data; deterministic engines do not emit fake LLM calls."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.contracts.common import Model


class LlmAudit(Model):
    lan_goi_id: str
    ca_id: str
    module: str
    provider: str
    model_version: str
    prompt_version: str
    schema_version: str
    input_sha256: str
    output_sha256: str | None = None
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    chi_phi: Decimal | None = None
    don_vi_tien: str | None = None
    trang_thai: Literal["SUCCESS", "ERROR"]
    ma_loi: str | None = None
    so_lan_thu: int = Field(ge=1)
    trace_id: str
    ngay_goi: datetime
