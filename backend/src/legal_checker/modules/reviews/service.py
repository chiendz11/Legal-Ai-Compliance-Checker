"""Step 8 / BR-14, BR-18: authorize reviewers and append events without replacing AI output."""

from typing import Protocol

from legal_checker.shared.contracts.review import HumanReview


class HumanReviewService(Protocol):
    def append_review(self, review: HumanReview) -> HumanReview: ...
    def effective_result(self, ca_id: str, target_id: str) -> dict[str, object]: ...
