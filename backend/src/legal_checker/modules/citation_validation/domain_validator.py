"""Whether a cited document's field fits the contract. Mismatch needs positive evidence."""

from collections.abc import Mapping
from typing import Any, Literal

from legal_checker.shared.contracts.document_intelligence import ContractProfile

DomainStatus = Literal["MATCH", "MISMATCH", "UNKNOWN"]

# Team policy: catalog `linh_vuc` prefixes that govern an apartment/real-estate sale.
DEFAULT_DOMAIN_PREFIXES: Mapping[str, tuple[str, ...]] = {
    "REAL_ESTATE_HOUSING": (
        "NHAO",
        "KDBDS",
        "BVNTD",
        "CAN_HO",
        "MODEL",
        "HIEU_LUC_NHA_O_BDS",
        "DAN_SU",
    ),
    "REAL_ESTATE": ("KDBDS", "BVNTD", "HIEU_LUC_NHA_O_BDS", "DAN_SU"),
}
# Social-housing documents fit only when the contract is evidenced social housing.
_SOCIAL_HOUSING = "NOXH"


def contract_domain(profile: ContractProfile, contract_types: Mapping[str, dict]) -> str | None:
    row = contract_types.get(profile.profile.loai_hop_dong_id or "")
    return row.get("legal_domain") if row else None


def validate_domain(
    document: dict[str, Any],
    profile: ContractProfile,
    contract_types: Mapping[str, dict],
    prefixes: Mapping[str, tuple[str, ...]] = DEFAULT_DOMAIN_PREFIXES,
) -> tuple[DomainStatus, str]:
    field = (document.get("linh_vuc") or "").upper()
    domain = contract_domain(profile, contract_types)
    if not field or domain not in prefixes:
        return "UNKNOWN", f"document field {field or '?'} / contract domain {domain or '?'}"
    if field.startswith(_SOCIAL_HOUSING):
        social = profile.profile.la_nha_o_xa_hoi
        if social is None:
            return "UNKNOWN", "social-housing document; contract social-housing status unknown"
        if social:
            return "MATCH", "social-housing document cited in a social-housing contract"
        return "MISMATCH", "social-housing document cited in a non-social-housing contract"
    if field.startswith(prefixes[domain]):
        return "MATCH", f"{field} governs {domain}"
    # Arbitration, e-transactions and similar fields depend on the clause, not the contract.
    return "UNKNOWN", f"{field} may apply to specific clauses of a {domain} contract"
