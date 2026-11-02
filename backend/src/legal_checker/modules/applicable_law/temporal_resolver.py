"""Step 3A / BR-05: resolve versions and transition rules without changing scope ownership."""

from collections.abc import Mapping
from datetime import date
from typing import Any, Protocol

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
# phien_ban_yeu_cau.loai_moc_ap_dung → C02 time marker. Signing never stands in for an event
# date: payment rules use the collection marker even when the signing date is known.
DEFAULT_MARKER_TYPES: dict[str, str] = {
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

    Scope-owned fields and the checklist are copied unchanged. Several versions in force,
    an unknown date or an unverified marker type stay UNKNOWN; nothing picks "the first".
    A requirement with no version yet in force at a known date is NOT_APPLICABLE.
    """

    def __init__(
        self,
        marker_types: Mapping[str, str] | None = None,
        family_events: Mapping[str, str] | None = None,
    ):
        self.marker_types = DEFAULT_MARKER_TYPES if marker_types is None else marker_types
        self.family_events = DEFAULT_FAMILY_EVENTS if family_events is None else family_events

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
        versions_by_family: dict[str, list[dict]] = {}
        for version in knowledge.versions.values():
            versions_by_family.setdefault(version["requirement_id"], []).append(version)
        markers: dict[str, list[ProfileTimeMarker]] = {}
        for marker in profile.time_markers:
            markers.setdefault(marker.loai_moc, []).append(marker)
        return [
            self.resolve_one(context, profile, item, versions_by_family, markers, knowledge)
            for item in scope
        ]

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
        elif marker is None:
            details["version"] = f"{len(found)} {marker_type} markers in C02; need exactly one"
        elif day is None:
            details["version"] = (
                f"{marker_type} date unknown; another marker is not used as a substitute"
            )
        else:
            active = [v for v in candidates if in_force(v, day)]
            confirmed = [v for v in active if group_of(v) == "MATCH"]
            starts = [as_date(v.get("hieu_luc_tu")) for v in candidates]
            if len(active) == 1 or len(confirmed) == 1:
                version = active[0] if len(active) == 1 else confirmed[0]
                version_status = "RESOLVED"
                if item.scope_status == "MATCH" and group_of(version) == "MATCH":
                    applicability = "CONFIRMED"
                details["version"] = (
                    f"{version['requirement_version_id']} in force on {day} "
                    f"[{version.get('hieu_luc_tu')}, {version.get('hieu_luc_den') or '∞'})"
                )
                if applicability != "CONFIRMED":
                    details["applicability"] = (
                        f"version group {version.get('nhom_phien_ban')} scope is "
                        f"{group_of(version)}"
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
            | details,
        )
