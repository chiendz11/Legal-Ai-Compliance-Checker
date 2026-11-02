"""Step 8 / BR-14, BR-18: append C12 review events to one run without replacing AI output.

Reviewable targets are the run's machine findings (C07, C08, C09, C10, C11). An OVERRIDE may
change only a few display-level fields and must stay schema-valid; the machine output is kept
as is and the reviewed value is an *effective* layer on top. Every review states the hash of
the effective target it saw (`expected_target_sha256`), so concurrent edits are rejected
instead of silently overwriting each other.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from legal_checker.shared.contracts.aggregation import RequirementResult
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.recommendation import Recommendation
from legal_checker.shared.contracts.review import HumanReview
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.contracts.workflow import AssessmentDraft

NO_REVIEW = "none"
ACTIONS = ("CONFIRM", "OVERRIDE", "REQUEST_MORE_EVIDENCE", "REJECT", "COMMENT")
# A target whose latest decisive review is one of these blocks publication.
BLOCKING = ("REQUEST_MORE_EVIDENCE", "REJECT")


@dataclass(frozen=True)
class TargetKind:
    """Where a reviewable output lives in the draft and which fields a reviewer may set."""

    source: str  # "evaluation" payload attribute or draft attribute
    attribute: str
    key: str
    model: type[BaseModel]
    editable: tuple[str, ...]


TARGETS: dict[str, TargetKind] = {
    "ket_qua_tieu_chi": TargetKind(
        "evaluation", "criterion_results", "ket_qua_id", CriterionResult, ("finding", "giai_thich")
    ),
    "ket_qua_tuan_thu": TargetKind(
        "evaluation", "requirement_results", "tuan_thu_id", RequirementResult, ("status",)
    ),
    "phat_hien_vien_dan": TargetKind(
        "draft", "citation_findings", "finding_id", CitationValidation, ("status", "ly_do")
    ),
    "ket_qua_rui_ro": TargetKind(
        "evaluation", "risks", "ket_qua_rui_ro_id", RiskResult, ("severity", "giai_thich")
    ),
    "khuyen_nghi_danh_gia": TargetKind(
        "evaluation",
        "recommendations",
        "khuyen_nghi_ca_id",
        Recommendation,
        ("noi_dung", "uu_tien"),
    ),
}


class ReviewError(ValueError):
    """Invalid review request (unknown target, bad override, wrong action payload)."""


class StaleReview(ValueError):
    """The target changed since the reviewer loaded it."""


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def review_revision(events: list[HumanReview]) -> str:
    """Identifies the exact ordered set of reviews a report or publication is based on."""
    if not events:
        return NO_REVIEW
    return f"r{len(events)}-{digest([e.review_id for e in events])[:12]}"


def machine_targets(draft: AssessmentDraft) -> dict[tuple[str, str], dict[str, Any]]:
    targets = {}
    for kind_name, kind in TARGETS.items():
        holder = draft.evaluation.payload if kind.source == "evaluation" else draft
        for item in getattr(holder, kind.attribute):
            data = item.model_dump(mode="json")
            targets[(kind_name, data[kind.key])] = data
    return targets


@dataclass
class TargetState:
    kind: str
    target_id: str
    machine: dict[str, Any]
    overrides: dict[str, Any] = field(default_factory=dict)
    reviews: list[HumanReview] = field(default_factory=list)

    @property
    def effective(self) -> dict[str, Any]:
        return {**self.machine, **self.overrides}

    @property
    def sha256(self) -> str:
        return digest(self.effective)

    @property
    def latest_decision(self) -> str | None:
        decisive = [r.action for r in self.reviews if r.action != "COMMENT"]
        return decisive[-1] if decisive else None


def target_states(
    draft: AssessmentDraft, events: list[HumanReview]
) -> dict[tuple[str, str], TargetState]:
    states = {
        key: TargetState(key[0], key[1], data) for key, data in machine_targets(draft).items()
    }
    for event in events:
        state = states.get((event.target.doi_tuong_loai, event.target.doi_tuong_id))
        if state is None:
            continue
        state.reviews.append(event)
        if event.action == "OVERRIDE":
            state.overrides.update(event.after)
    return states


def check_review(
    state: TargetState | None, action: str, after: dict[str, Any], expected_sha256: str
) -> None:
    if state is None:
        raise ReviewError("Review target is not an output of this run")
    if action not in ACTIONS:
        raise ReviewError(f"Unknown review action {action}")
    if state.sha256 != expected_sha256:
        raise StaleReview("The finding changed since it was loaded; reload and review again")
    if action != "OVERRIDE":
        if after:
            raise ReviewError(f"{action} takes no `after` values")
        return
    kind = TARGETS[state.kind]
    unknown = set(after) - set(kind.editable)
    if not after or unknown:
        raise ReviewError(
            f"OVERRIDE may set only {', '.join(kind.editable)}"
            + (f"; not {', '.join(sorted(unknown))}" if unknown else "")
        )
    try:
        kind.model.model_validate({**state.effective, **after})
    except ValidationError as error:
        raise ReviewError(f"OVERRIDE is not schema-valid: {error.errors()[0]['msg']}") from error
    if all(state.effective.get(key) == value for key, value in after.items()):
        raise ReviewError("OVERRIDE does not change anything; use CONFIRM")


def publication_blockers(
    states: dict[tuple[str, str], TargetState],
) -> list[dict[str, str]]:
    """What still needs a reviewer before a report may be published."""
    blockers = []
    for state in states.values():
        decision = state.latest_decision
        if decision in BLOCKING:
            blockers.append(
                {"doi_tuong_loai": state.kind, "doi_tuong_id": state.target_id, "reason": decision}
            )
            continue
        effective = state.effective
        serious = (
            state.kind == "ket_qua_tuan_thu"
            and effective.get("status") in ("NON_COMPLIANT", "PARTIAL")
        ) or (state.kind == "ket_qua_rui_ro" and effective.get("severity") in ("HIGH", "CRITICAL"))
        if serious and decision not in ("CONFIRM", "OVERRIDE"):
            blockers.append(
                {
                    "doi_tuong_loai": state.kind,
                    "doi_tuong_id": state.target_id,
                    "reason": "UNCONFIRMED_SERIOUS_FINDING",
                }
            )
    return blockers


def review_layer(
    states: dict[tuple[str, str], TargetState], events: list[HumanReview]
) -> dict[str, Any]:
    """Audit section of a reviewed report: events plus effective values, machine data untouched."""
    effective: dict[str, dict[str, dict[str, Any]]] = {}
    decisions: dict[str, dict[str, str]] = {}
    for state in states.values():
        if state.overrides:
            effective.setdefault(state.kind, {})[state.target_id] = state.overrides
        if state.latest_decision:
            decisions.setdefault(state.kind, {})[state.target_id] = state.latest_decision
    return {
        "review_revision": review_revision(events),
        "events": [event.model_dump(mode="json") for event in events],
        "effective": effective,
        "decisions": decisions,
    }
