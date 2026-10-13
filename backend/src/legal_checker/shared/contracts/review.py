"""C12: append-only human review events; AI output remains an immutable original."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from legal_checker.shared.contracts.common import Model


class ReviewTarget(Model):
    doi_tuong_loai: str
    doi_tuong_id: str


class HumanReview(Model):
    review_id: str
    ca_id: str
    target: ReviewTarget
    actor_id: str
    action: Literal["CONFIRM", "OVERRIDE", "REQUEST_MORE_EVIDENCE", "REJECT", "COMMENT"]
    before: dict[str, Any]
    after: dict[str, Any]
    reason: str = Field(min_length=1)
    reviewed_at: datetime
    phien_ban_id: str
