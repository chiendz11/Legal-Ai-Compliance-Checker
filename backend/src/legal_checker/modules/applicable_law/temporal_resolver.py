"""Step 3A / BR-05: resolve versions and transition rules without changing scope ownership."""

from collections.abc import Mapping
from datetime import date
from typing import Any, Protocol

from legal_checker.modules.applicable_law.catalog_policy import MARKERS, read_policy, selection_date
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import ContractProfile, ProfileTimeMarker
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.shared.contracts.temporal import ApplicableRequirement


class TemporalResolver(Protocol):
    def resolve(
        self,
        context: Context,
        profile: ContractProfile,
        scope: list[ScopeResolution],
        knowledge: KnowledgeSnapshot,
    ) -> list[ApplicableRequirement]: ...


RESOLUTION_METHOD = "CATALOG_MARKER_VERSION_INTERVAL"
_UNVERIFIED_MARKER = "CHUA_XAC_MINH"
# phien_ban_yeu_cau.loai_moc_ap_dung → C02 marker. Legacy payment rules keep their
# collection semantics. Versioned contract-review policies explicitly separate the date
# selecting the legal regime from evidence of later payment/performance.
DEFAULT_MARKER_TYPES: dict[str, str] = {
    **{name: name for name in MARKERS},
    "NGAY_XAC_LAP_HOAC_SU_DUNG_MAU": "SIGNING",
    "NGAY_THOA_THUAN_VA_NGAY_THU_TIEN": "COLLECTION",
    "NGAY_GIAO_KET_VA_MOC_GIAO_THU_NHAN_TIEN": "COLLECTION",
}
# Team policy: payment caps tied to a specific collection event instead of any collection.
DEFAULT_FAMILY_EVENTS: dict[str, str] = {
    "FAM_PRE_CERT_CAP": "PRE_CERTIFICATE_COLLECTION",
    "FAM_PRE_HANDOVER_CAP": "PRE_HANDOVER_COLLECTION",
}


def as_date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def in_force(version: Mapping[str, Any], day: date) -> bool:
    """Half-open interval [hieu_luc_tu, hieu_luc_den); a missing end is open-ended."""
    start, end = as_date(version.get("hieu_luc_tu")), as_date(version.get("hieu_luc_den"))
    return start is not None and start <= day and (end is None or day < end)


class CatalogTemporalResolver:
    """Pick the requirement version in force at the obligation's own time marker.

    Scope-owned fields and the checklist are copied unchanged. Concurrent sources in a
    versioned policy, an unknown date or an unverified marker stay UNKNOWN; nothing picks
    "the first". Legacy catalogs retain their existing single-confirmed-group behavior.
    A requirement with no version yet in force at a known date is NOT_APPLICABLE.
    """

    def __init__(
        self,
        marker_types: Mapping[str, str] | None = None,
        family_events: Mapping[str, str] | None = None,
        case=None,
    ):
        self.marker_types = DEFAULT_MARKER_TYPES if marker_types is None else marker_types
        self.family_events = DEFAULT_FAMILY_EVENTS if family_events is None else family_events
        self.case = case

    def marker_type(self, requirement_id: str, versions: list[dict]) -> str | None:
        """One marker type per family; old versions marked CHUA_XAC_MINH inherit it."""
        kinds = {
            v["loai_moc_ap_dung"]
            for v in versions
            if v.get("loai_moc_ap_dung") and v["loai_moc_ap_dung"] != _UNVERIFIED_MARKER
        }
        if len(kinds) != 1:
            return None
        marker = self.marker_types.get(kinds.pop())
        if marker == "COLLECTION":
            return self.family_events.get(requirement_id, marker)
        return marker

    def resolve(
        self,
        context: Context,
        profile: ContractProfile,
        scope: list[ScopeResolution],
        knowledge: KnowledgeSnapshot,
    ) -> list[ApplicableRequirement]:
        if self.case and (
            self.case.ca_id != context.ca_id or self.case.hop_dong_id != profile.hop_dong_id
        ):
            raise ValueError("Declared C01 marker belongs to another assessment")
        versions_by_family: dict[str, list[dict]] = {}
        for version in knowledge.versions.values():
            versions_by_family.setdefault(version["requirement_id"], []).append(version)
        markers: dict[str, list[ProfileTimeMarker]] = {}
        for marker in profile.time_markers:
            markers.setdefault(marker.loai_moc, []).append(marker)
        from legal_checker.modules.applicable_law.historical_coverage import (
            resolve_historical_branches,
        )

        rows = [
            self.resolve_one(context, profile, item, versions_by_family, markers, knowledge)
            for item in scope
        ]
        return resolve_historical_branches(rows, knowledge)

    def resolve_one(
        self,
        context: Context,
        profile: ContractProfile,
        item: ScopeResolution,
        versions_by_family: dict[str, list[dict]],
        markers: dict[str, list[ProfileTimeMarker]],
        knowledge: KnowledgeSnapshot,
    ) -> ApplicableRequirement:
        family_versions = sorted(
            versions_by_family.get(item.requirement_id, []),
            key=lambda v: (str(v.get("hieu_luc_tu")), v["requirement_version_id"]),
        )
        group_status = item.dieu_kien_snapshot_json.get("group_status") or {}

        def group_of(version: dict) -> str:
            # Without per-group scope detail, fall back to the family-level scope status.
            return group_status.get(str(version.get("nhom_phien_ban")), item.scope_status)

        candidates = [v for v in family_versions if group_of(v) != "NO_MATCH"]
        marker_type = self.marker_type(item.requirement_id, family_versions)
        found = markers.get(marker_type, []) if marker_type else []
        marker = found[0] if len(found) == 1 else None
        day = marker.ngay if marker else None
        declared = None
        declared_conflict = None
        if self.case:
            timing = self.case.assessment_context
            kind = {"NGAY_GIAO_KET": "SIGNING", "NGAY_SU_DUNG_MAU": "TEMPLATE_USE"}.get(
                timing.loai_moc_ap_dung, timing.loai_moc_ap_dung
            )
            if timing.moc_ap_dung is not None and kind == marker_type:
                declared = {
                    "source": "C01_DECLARED",
                    "marker_type": kind,
                    "date": timing.moc_ap_dung.isoformat(),
                    "basis": "PLANNED_DRAFT_SCENARIO"
                    if timing.review_mode == "DRAFT_REVIEW"
                    else "CALLER_DECLARED",
                    "declared_by": self.case.created_by,
                    "ca_id": context.ca_id,
                }
                if day is not None and day != timing.moc_ap_dung:
                    declared_conflict = "C01 date conflicts with evidenced C02 marker"
                    day = None
                else:
                    day = timing.moc_ap_dung
                    # Do not pretend a caller declaration was extracted from the PDF.
                    marker = None

        policy_issue = declared_conflict
        policies = []
        basis_day = day
        try:
            policies = [p for v in candidates if (p := read_policy(v)) is not None]
            if policies and (
                len(policies) != len(candidates)
                or any(p.selection_marker != marker_type for p in policies)
            ):
                policy_issue = "inconsistent versioned legal policy within family"
            elif policies and day is not None:
                basis_day, selection_issue = selection_date(profile, day, policies)
                policy_issue = policy_issue or selection_issue
        except (ValueError, TypeError):
            policy_issue = "invalid or unsupported versioned legal policy"

        version: dict | None = None
        version_status, applicability = "UNKNOWN", "UNKNOWN"
        details: dict[str, str] = {}
        if item.scope_status == "NO_MATCH":
            applicability = "NOT_APPLICABLE"
            details["version"] = "not resolved: scope is NO_MATCH"
        elif not candidates:
            details["version"] = "no requirement version for an open scope group"
        elif marker_type is None:
            details["version"] = "marker type unverified for every version of this family"
        elif declared_conflict:
            details["version"] = declared_conflict
        elif marker is None and declared is None:
            details["version"] = f"{len(found)} {marker_type} markers in C02; need exactly one"
        elif day is None:
            details["version"] = (
                f"{marker_type} date unknown; another marker is not used as a substitute"
            )
        elif policy_issue:
            details["version"] = policy_issue
        else:
            active = [v for v in candidates if in_force(v, basis_day)]
            confirmed = [v for v in active if group_of(v) == "MATCH"]
            starts = [as_date(v.get("hieu_luc_tu")) for v in candidates]
            if len(active) == 1 or (len(confirmed) == 1 and not policies):
                version = active[0] if len(active) == 1 else confirmed[0]
                version_status = "RESOLVED"
                if item.scope_status == "MATCH" and group_of(version) == "MATCH":
                    applicability = "CONFIRMED"
                details["version"] = (
                    f"{version['requirement_version_id']} in force on {basis_day} "
                    f"[{version.get('hieu_luc_tu')}, {version.get('hieu_luc_den') or '∞'})"
                )
                if applicability != "CONFIRMED":
                    details["applicability"] = (
                        f"version group {version.get('nhom_phien_ban')} scope is "
                        f"{group_of(version)}"
                    )
                policy = read_policy(version)
                if policy is not None and not policy.criteria_ready:
                    version = None
                    version_status, applicability = "UNKNOWN", "UNKNOWN"
                    details["version"] = "catalog version has no approved executable criteria"
                if basis_day != day:
                    details["transition"] = (
                        f"Article 83(5): signing/event date {day}; grandfathered regime "
                        f"selected at {basis_day}; no substitute for performance evidence"
                    )
            elif not active and all(s is not None and day < s for s in starts):
                if len(family_versions) == 1:
                    # The family's only version introduced the requirement: it did not exist yet.
                    applicability = "NOT_APPLICABLE"
                    details["version"] = (
                        f"requirement introduced on {min(starts)}, after {day}; not in force"
                    )
                else:
                    # A version chain that starts later is a catalog coverage gap, not absence.
                    details["version"] = (
                        f"{day} is before catalog coverage of this family (from {min(starts)})"
                    )
            elif not active:
                details["version"] = f"no version in force on {day}"
            else:
                ids = ", ".join(v["requirement_version_id"] for v in active)
                details["version"] = f"{len(active)} versions in force on {day}: {ids}"

        # Unresolved rows keep an unconfirmed pointer so Retrieval/Compliance can still load
        # criteria (same convention as the seeded C05): the newest candidate, preferring a
        # MATCH scope group. version_status stays UNKNOWN and candidate_version_only=True.
        pointer = version
        if pointer is None and applicability != "NOT_APPLICABLE" and candidates:
            preferred = [v for v in candidates if group_of(v) == "MATCH"] or candidates
            pointer = preferred[-1]
        summary = f"{version_status}/{applicability}: {details['version']}"
        return ApplicableRequirement(
            yeu_cau_ca_id=item.yeu_cau_ca_id,
            ca_id=item.ca_id,
            requirement_id=item.requirement_id,
            requirement_version_id=pointer["requirement_version_id"] if pointer else None,
            # Scope owns nhom_phien_ban (checked by workflows.handoffs.validate_legal); the
            # selected version's own group is recorded in nguon_snapshot_json instead.
            nhom_phien_ban=item.nhom_phien_ban,
            scope_status=item.scope_status,
            version_status=version_status,
            applicability_status=applicability,
            moc_id=marker.moc_id if marker else None,
            loai_moc=marker_type,
            moc_ap_dung=day,
            resolution_method=RESOLUTION_METHOD,
            profile_snapshot_json=item.profile_snapshot_json,
            dieu_kien_snapshot_json=item.dieu_kien_snapshot_json,
            nguon_snapshot_json={
                "candidate_version_only": version is None,
                "knowledge_sha256": knowledge.sha256,
                "legal_gold": False,
                "source_document_id": profile.hop_dong_id,
                "candidate_version_ids": [v["requirement_version_id"] for v in candidates],
                "version_group": pointer.get("nhom_phien_ban") if pointer else None,
                "marker_evidence": marker.trich_xuat_id if marker else None,
                **({"assessment_marker": declared} if declared else {}),
                "legal_policy_id": policies[0].policy_id if policies else None,
                "regime_selection_date": basis_day.isoformat() if policies and basis_day else None,
                "version_basis": (
                    {
                        "source_van_ban_id": version.get("source_van_ban_id"),
                        "dieu_khoan_id": version.get("dieu_khoan_id"),
                        "hieu_luc_tu": str(version.get("hieu_luc_tu")),
                        "hieu_luc_den": (
                            str(version["hieu_luc_den"]) if version.get("hieu_luc_den") else None
                        ),
                        "can_xac_minh_chuyen_tiep": version.get("can_xac_minh_chuyen_tiep"),
                        "quy_tac_chuyen_tiep": version.get("quy_tac_chuyen_tiep"),
                    }
                    if version
                    else None
                ),
            },
            phien_ban_id=context.phien_ban_id,
            reason={"mode": RESOLUTION_METHOD, "summary": summary, "scope": item.scope_reason}
            | (
                {"date_source": "C01 caller declaration; not proof of actual execution"}
                if declared
                else {}
            )
            | details,
        )
