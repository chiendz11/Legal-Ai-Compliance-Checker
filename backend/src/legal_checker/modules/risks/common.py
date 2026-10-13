from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.ids import stable_id


def _risk(request, knowledge, rule, source, reason, evidence, basis, risk_type):
    catalog = knowledge.risks[rule["rui_ro_id"]]
    source_id = source.ket_qua_tieu_chi_id or source.citation_finding_id
    return RiskResult(
        ket_qua_rui_ro_id=stable_id(request, "RISK", rule["quy_tac_id"] + source_id),
        ca_id=request.ca_id,
        risk_type=risk_type,
        rui_ro_id=catalog["rui_ro_id"],
        severity=catalog["muc_do_co_so"],
        source=source,
        quy_tac_id=rule["quy_tac_id"],
        giai_thich=reason,
        risk_snapshot=catalog,
        rule_snapshot_json=rule,
        evidence_ids=evidence,
        legal_basis_ids=basis,
    )
