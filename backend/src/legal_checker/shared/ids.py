from uuid import NAMESPACE_URL, uuid5

from legal_checker.shared.contracts.common import Context


def stable_id(context: Context, kind: str, key: str) -> str:
    return f"{kind}_{uuid5(NAMESPACE_URL, f'{context.ca_id}/{context.run_id}/{kind}/{key}')}"


def requirement_instance_id(ca_id: str, requirement_id: str) -> str:
    """C04/C05 `yeu_cau_ca_id`; same format as the seeded reference rows."""
    return f"{ca_id}_{requirement_id}"


def citation_finding_id(ca_id: str, hop_dong_id: str, vien_dan_id: str) -> str:
    """C09 `finding_id`; HD360_001_LS2_CIT_00001 → CA360_001_LS2_CIT_FIND_00001 (reference)."""
    prefix = f"{hop_dong_id}_"
    if vien_dan_id.startswith(prefix) and "CIT_" in vien_dan_id:
        return f"{ca_id}_{vien_dan_id[len(prefix) :].replace('CIT_', 'CIT_FIND_', 1)}"
    return f"{ca_id}_{vien_dan_id}_FIND"


def retrieval_id(yeu_cau_ca_id: str, tieu_chi_id: str, rank: int) -> str:
    """C06 `truy_xuat_id` for one ranked chunk of one criterion."""
    return f"{yeu_cau_ca_id}/{tieu_chi_id}/R{rank}"
