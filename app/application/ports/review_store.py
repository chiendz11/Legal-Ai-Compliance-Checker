"""C12 persistence stays append-only and separate from original AI results."""

from typing import Protocol

from app.contracts.review import HumanReview


class ReviewStore(Protocol):
    def append(self, event: HumanReview) -> HumanReview: ...
    def events(self, ca_id: str, target_id: str) -> list[HumanReview]: ...
