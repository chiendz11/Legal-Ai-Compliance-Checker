"""Step 3A / BR-03, BR-04, BR-06: independent from contract-authored citations."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import ContractProfile
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.shared.ids import requirement_instance_id

ScopeStatus = Literal["MATCH", "NO_MATCH", "UNKNOWN"]

# Profile booleans are typed bool, catalog conditions use CO/KHONG text (and sometimes JSON
# booleans). Both sides are normalized to the catalog vocabulary before comparison.
_BOOLEAN_TEXT = {True: "CO", False: "KHONG"}
_UNKNOWN_TEXT = {"", "UNKNOWN", "CHUA_RO", "NULL", "NONE"}
_GROUPED = "THEO_NHOM_PHIEN_BAN_KHONG_LOAI_TRU_NGUON_DONG_THOI"
_ALL_MANDATORY = "ALL_MANDATORY"
# Catalog marks clauses whose party capacity still has to be verified ("không chọn chỉ
# theo tên loại"); without a party condition such a clause cannot reach MATCH.
_PARTY_CAPACITY_PENDING = "CAN_XAC_MINH_TU_CACH_CAC_BEN"
_PARTY_FIELD_PREFIXES = ("BEN_BAN.", "BEN_MUA.", "ben_ban_", "ben_mua_")
# Team policy, not catalog data: how party capacity is verified when a pending clause has no
# party condition. Keys are a requirement_id (checked first) or a version group. The policy
# only confirms; it never turns a clause into NO_MATCH.
# - NHAO: housing-law obligations (maintenance fee, warranty) bind a developer selling a
#   newly built apartment.
# - KDBDS: real-estate-business law binds a business seller in a KINH_DOANH_BDS transaction.
# - Payment caps before certificate/handover (Điều 25, future housing) reuse the conditions the
#   catalog states for their sibling FAM_FIRST_PAYMENT_CAP.
_BUSINESS_SALE = (
    {"field": "BEN_BAN.la_chu_the_kinh_doanh", "op": "EQ", "value": "CO"},
    {"field": "che_do_giao_dich", "op": "EQ", "value": "KINH_DOANH_BDS"},
)
_FUTURE_COMMERCIAL_SALE = (
    *_BUSINESS_SALE,
    {"field": "tinh_trang_tai_san", "op": "EQ", "value": "HINH_THANH_TRONG_TUONG_LAI"},
    {"field": "la_nha_o_xa_hoi", "op": "EQ", "value": "KHONG"},
)
DEFAULT_PARTY_CAPACITY_CHECKS: dict[str, tuple[dict[str, Any], ...]] = {
    "NHAO": (
        {"field": "ben_ban_la_chu_dau_tu", "op": "EQ", "value": "CO"},
        {"field": "la_nha_xay_moi", "op": "EQ", "value": "CO"},
    ),
    "KDBDS": _BUSINESS_SALE,
    "FAM_PRE_CERT_CAP": _FUTURE_COMMERCIAL_SALE,
    "FAM_PRE_HANDOVER_CAP": _FUTURE_COMMERCIAL_SALE,
}
# Team policy: commercial-housing payment/content families. FAM_FIRST_PAYMENT_CAP states the
# exclusion in the catalog (la_nha_o_xa_hoi=false, NOXH needs a separate checklist); sibling
# families omit it. Only evidenced social housing excludes; unknown values change nothing.
DEFAULT_COMMERCIAL_ONLY_REQUIREMENTS = frozenset(
    {
        "FAM_APT_COMMERCIAL_CONTENT",
        "FAM_APT_DEPOSIT",
        "FAM_FIRST_PAYMENT_CAP",
        "FAM_PRE_CERT_CAP",
        "FAM_PRE_HANDOVER_CAP",
    }
)


class ScopeResolver(Protocol):
    def resolve(
        self, context: Context, profile: ContractProfile, knowledge: KnowledgeSnapshot
    ) -> list[ScopeResolution]: ...


@dataclass(frozen=True)
class FieldValue:
    """A profile value plus the evidence it came from; value None means unknown."""

    value: Any
    evidence: tuple[str, ...] = ()
    note: str | None = None


@dataclass
class Check:
    field: str
    op: str
    expected: Any
    actual: Any
    result: bool | None
    evidence: tuple[str, ...] = ()
    note: str | None = None

    def as_json(self) -> dict[str, Any]:
        row = {
            "field": self.field,
            "op": self.op,
            "expected": self.expected,
            "actual": self.actual,
            "result": "UNKNOWN" if self.result is None else self.result,
            "evidence": list(self.evidence),
        }
        if self.note:
            row["note"] = self.note
        return row


@dataclass
class ClauseResult:
    pham_vi_id: str
    nhom_phien_ban: str | None
    status: ScopeStatus
    checks: list[Check] = field(default_factory=list)
    note: str | None = None


def normalize(value: Any) -> Any:
    if isinstance(value, bool):
        return _BOOLEAN_TEXT[value]
    if isinstance(value, str):
        text = value.strip()
        return None if text.upper() in _UNKNOWN_TEXT else text
    return value


def kleene_and(statuses: Iterable[ScopeStatus]) -> ScopeStatus:
    statuses = list(statuses)
    if "NO_MATCH" in statuses:
        return "NO_MATCH"
    if "UNKNOWN" in statuses or not statuses:
        return "UNKNOWN"
    return "MATCH"


def kleene_or(statuses: Iterable[ScopeStatus]) -> ScopeStatus:
    statuses = list(statuses)
    if "MATCH" in statuses:
        return "MATCH"
    if "UNKNOWN" in statuses or not statuses:
        return "UNKNOWN"
    return "NO_MATCH"


def get_field(profile: ContractProfile, name: str) -> FieldValue:
    """Resolve `field` or `ROLE.field` from C02; missing or ambiguous values stay unknown."""
    if "." in name:
        role, attribute = name.split(".", 1)
        subjects = [s for s in profile.subjects if s.vai_tro == role]
        if not subjects:
            return FieldValue(None, note=f"no {role} subject in C02")
        if attribute not in type(subjects[0]).model_fields:
            return FieldValue(None, note=f"C02 subjects have no field {attribute}")
        values = {normalize(getattr(s, attribute)) for s in subjects}
        if len(values) != 1:
            return FieldValue(None, note=f"{len(subjects)} {role} subjects disagree")
        evidence = tuple(s.doan_bang_chung_id for s in subjects if s.doan_bang_chung_id)
        return FieldValue(values.pop(), evidence)

    if name not in type(profile.profile).model_fields:
        return FieldValue(None, note=f"C02 profile has no field {name}")
    evidence = tuple(
        evidence_id
        for fact in profile.facts
        if fact.ten_truong == f"profile.{name}"
        for evidence_id in fact.evidence_ids
    )
    return FieldValue(normalize(getattr(profile.profile, name)), evidence)


def is_descendant(type_id: str, ancestor_id: str, contract_types: dict[str, dict]) -> bool | None:
    """Walk `loai_cha_id`; a type missing from the catalog cannot be placed, so unknown."""
    seen = set()
    current = type_id
    while current is not None:
        if current == ancestor_id:
            return True
        if current in seen or current not in contract_types:
            return None
        seen.add(current)
        current = contract_types[current].get("loai_cha_id")
    return False


def evaluate_check(
    condition: dict[str, Any],
    profile: ContractProfile,
    contract_types: dict[str, dict],
    require_evidence: bool,
) -> Check:
    name, op = condition["field"], condition["op"]
    expected = normalize(condition["value"])
    found = get_field(profile, name)
    check = Check(name, op, expected, found.value, None, found.evidence, found.note)
    if found.value is None:
        return check
    if require_evidence and not found.evidence:
        check.note = "value has no source evidence in C02"
        return check
    if op == "EQ":
        check.result = found.value == expected
    elif op == "IS_OR_DESCENDANT_OF":
        check.result = is_descendant(found.value, expected, contract_types)
        if check.result is None:
            check.note = f"{found.value} is not in knowledge.loai_hop_dong"
    else:
        raise ValueError(f"Unsupported scope operator {op!r} for field {name!r}")
    return check


def evaluate_clause(
    clause: dict[str, Any],
    profile: ContractProfile,
    contract_types: dict[str, dict],
    party_capacity_checks: dict[str, tuple[dict[str, Any], ...]] | None = None,
) -> ClauseResult:
    condition = clause["dieu_kien_json"]
    if not isinstance(condition, dict) or not isinstance(condition.get("all"), list):
        raise ValueError(f"Scope clause {clause['pham_vi_id']} needs a dieu_kien_json.all list")
    require_evidence = bool(condition.get("scope_confirmed_requires_validated_facts"))
    checks = [
        evaluate_check(item, profile, contract_types, require_evidence) for item in condition["all"]
    ]
    status = kleene_and(
        "UNKNOWN" if c.result is None else ("MATCH" if c.result else "NO_MATCH") for c in checks
    )
    note = None
    if (
        status == "MATCH"
        and clause.get("loai_chu_the") == _PARTY_CAPACITY_PENDING
        and not any(c.field.startswith(_PARTY_FIELD_PREFIXES) for c in checks)
    ):
        policies = party_capacity_checks or {}
        policy = policies.get(clause.get("requirement_id")) or policies.get(
            clause.get("nhom_phien_ban")
        )
        party_checks = [
            evaluate_check(item, profile, contract_types, require_evidence) for item in policy or ()
        ]
        if party_checks and all(c.result is True for c in party_checks):
            note = "party capacity confirmed by team policy for group " + str(
                clause.get("nhom_phien_ban")
            )
        else:
            status = "UNKNOWN"
            note = f"loai_chu_the={_PARTY_CAPACITY_PENDING}; party capacity not confirmed" + (
                " by " + ", ".join(f"{c.field}={c.actual!r}" for c in party_checks)
                if party_checks
                else " (clause has no party condition)"
            )
        for check in party_checks:
            check.note = "team party-capacity policy"
        checks.extend(party_checks)
    return ClauseResult(clause["pham_vi_id"], clause.get("nhom_phien_ban"), status, checks, note)


def combine_clauses(mode: str, clauses: list[ClauseResult]) -> tuple[ScopeStatus, dict]:
    """ALL_MANDATORY: every clause. Grouped mode: AND within a version group, OR across groups;
    concurrent groups are kept for Temporal instead of excluding each other."""
    groups: dict[str | None, list[ClauseResult]] = {}
    for clause in clauses:
        groups.setdefault(clause.nhom_phien_ban, []).append(clause)
    by_group = {group: kleene_and(c.status for c in items) for group, items in groups.items()}
    if mode == _ALL_MANDATORY:
        return kleene_and(c.status for c in clauses), by_group
    if mode == _GROUPED:
        return kleene_or(by_group.values()), by_group
    raise ValueError(f"Unsupported che_do_ket_hop {mode!r}")


def reason(status: ScopeStatus, clauses: list[ClauseResult], by_group: dict) -> str:
    if not clauses:
        return "UNKNOWN: no scope clause in knowledge.pham_vi_ap_dung"
    if status == "MATCH":
        groups = sorted(str(g) for g, s in by_group.items() if s == "MATCH")
        notes = [c.note for c in clauses if c.status == "MATCH" and c.note]
        suffix = f" ({'; '.join(dict.fromkeys(notes))})" if notes else ""
        return f"MATCH: every condition met in group(s) {', '.join(groups)}{suffix}"
    wanted = "UNKNOWN" if status == "UNKNOWN" else "NO_MATCH"
    details = []
    for clause in clauses:
        if wanted == "UNKNOWN" and clause.note:
            details.append(f"{clause.nhom_phien_ban}: {clause.note}")
        for check in clause.checks:
            failed = check.result is None if wanted == "UNKNOWN" else check.result is False
            if failed:
                text = f"{check.field}={check.actual!r} vs {check.op} {check.expected!r}"
                details.append(f"{text} ({check.note})" if check.note else text)
    unique = list(dict.fromkeys(details))
    return f"{wanted}: " + "; ".join(unique[:5])


class CatalogScopeResolver:
    """Evaluate `pham_vi_ap_dung` predicates against C02 with three-valued logic.

    Missing facts give UNKNOWN, never NO_MATCH. Contract-authored citations are not an
    input, so a requirement can apply even if the contract never cites its law.
    `requirement_ids` limits the supported catalog; None evaluates every family.
    `party_capacity_checks` maps a version group to the C02 checks that confirm party capacity
    for clauses marked CAN_XAC_MINH_TU_CACH_CAC_BEN; pass {} to disable the team policy.
    `commercial_only_requirements` are families that a contract evidenced as social housing
    cannot match; pass () to disable that team policy.
    """

    def __init__(
        self,
        requirement_ids: Iterable[str] | None = None,
        party_capacity_checks: dict[str, tuple[dict[str, Any], ...]] | None = None,
        commercial_only_requirements: Iterable[str] | None = None,
    ):
        self.requirement_ids = None if requirement_ids is None else frozenset(requirement_ids)
        self.party_capacity_checks = (
            DEFAULT_PARTY_CAPACITY_CHECKS
            if party_capacity_checks is None
            else party_capacity_checks
        )
        self.commercial_only_requirements = frozenset(
            DEFAULT_COMMERCIAL_ONLY_REQUIREMENTS
            if commercial_only_requirements is None
            else commercial_only_requirements
        )

    def resolve(
        self, context: Context, profile: ContractProfile, knowledge: KnowledgeSnapshot
    ) -> list[ScopeResolution]:
        contract_types = {r["loai_hop_dong_id"]: r for r in knowledge.tables["loai_hop_dong"]}
        families = {r["requirement_id"]: r for r in knowledge.tables["yeu_cau_phap_ly"]}
        if self.requirement_ids is not None:
            unknown = self.requirement_ids - families.keys()
            if unknown:
                raise ValueError(f"Requirements not in knowledge: {sorted(unknown)}")
            families = {k: v for k, v in families.items() if k in self.requirement_ids}
        clauses_by_family: dict[str, list[dict]] = {}
        for row in knowledge.tables["pham_vi_ap_dung"]:
            clauses_by_family.setdefault(row["requirement_id"], []).append(row)

        # Same top-level keys as the seeded C04 snapshots, so downstream readers keep working.
        profile_snapshot = {
            "human_verified": False,
            "profile": profile.profile.model_dump(mode="json"),
        }
        results = []
        for requirement_id in sorted(families):
            clauses = [
                evaluate_clause(row, profile, contract_types, self.party_capacity_checks)
                for row in sorted(
                    clauses_by_family.get(requirement_id, []), key=lambda r: r["pham_vi_id"]
                )
            ]
            mode = families[requirement_id]["che_do_ket_hop"]
            status, by_group = combine_clauses(mode, clauses) if clauses else ("UNKNOWN", {})
            scope_reason = reason(status, clauses, by_group)
            exclusion = None
            if requirement_id in self.commercial_only_requirements:
                social = get_field(profile, "la_nha_o_xa_hoi")
                if social.value == "CO" and social.evidence:
                    exclusion = {
                        "policy": "SOCIAL_HOUSING_EXCLUDED_FROM_COMMERCIAL_REQUIREMENT",
                        "field": "la_nha_o_xa_hoi",
                        "value": social.value,
                        "evidence": list(social.evidence),
                        "status_before_exclusion": status,
                    }
                    status, by_group = "NO_MATCH", {g: "NO_MATCH" for g in by_group}
                    scope_reason = (
                        "NO_MATCH: social housing (la_nha_o_xa_hoi='CO') is excluded from "
                        "this commercial-housing requirement (team policy)"
                    )
            open_groups = [g for g, s in by_group.items() if s != "NO_MATCH"]
            results.append(
                ScopeResolution(
                    yeu_cau_ca_id=requirement_instance_id(context.ca_id, requirement_id),
                    ca_id=context.ca_id,
                    requirement_id=requirement_id,
                    nhom_phien_ban=open_groups[0] if len(open_groups) == 1 else None,
                    scope_status=status,
                    profile_snapshot_json={
                        **profile_snapshot,
                        "scope_fields": {
                            c.field: {"value": c.actual, "evidence": list(c.evidence)}
                            for clause in clauses
                            for c in clause.checks
                        },
                    },
                    dieu_kien_snapshot_json={
                        "checklist_exhaustive": False,
                        "unprovided_event_date_is_not_signing_date": True,
                        "che_do_ket_hop": mode,
                        "group_status": {str(g): s for g, s in by_group.items()},
                        "clauses": [
                            {
                                "pham_vi_id": c.pham_vi_id,
                                "nhom_phien_ban": c.nhom_phien_ban,
                                "status": c.status,
                                "note": c.note,
                                "checks": [check.as_json() for check in c.checks],
                            }
                            for c in clauses
                        ],
                        "exclusion": exclusion,
                    },
                    scope_reason=scope_reason,
                )
            )
        return results
