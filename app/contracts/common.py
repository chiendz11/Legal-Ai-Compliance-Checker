from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Finding = Literal["SATISFIED", "MISSING", "VIOLATED", "UNKNOWN"]
RequirementStatus = Literal["COMPLIANT", "PARTIAL", "NON_COMPLIANT", "INSUFFICIENT"]
RiskType = Literal["COMPLIANCE", "CITATION", "VERIFICATION"]
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "REVIEW_REQUIRED"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Context(Model):
    contract_version: Literal["1.0"] = "1.0"
    ca_id: str = Field(min_length=1)
    phien_ban_id: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    legal_knowledge_version: str = Field(min_length=1)
    knowledge_snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    run_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)


class DeploymentPin(Model):
    phien_ban_id: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    legal_knowledge_version: str = Field(min_length=1)
