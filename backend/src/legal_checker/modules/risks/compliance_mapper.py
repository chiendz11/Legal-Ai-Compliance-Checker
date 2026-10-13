import json

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.risks.common import _risk
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.risk import RiskSource


def compliance_risks(
    request: Context, knowledge: KnowledgeSnapshot, criteria: list[CriterionResult]
):
    results = []
    for criterion in criteria:
        if criterion.excluded or criterion.finding == "SATISFIED":
            continue
        for rule in knowledge.tables["quy_tac_rui_ro"]:
            if (
                rule["nhanh"] != "COMPLIANCE"
                or rule["tieu_chi_id"] != criterion.tieu_chi_id
                or rule["trigger_status"] != criterion.finding
            ):
                continue
            trigger = json.loads(rule["trigger_json"])
            if trigger.get("enabled") is not True:
                continue
            # Recheck workbook gates; callers cannot turn a retrieval miss into a risk.
            gate_values = criterion.gates.model_dump()
            gate_values["mandatory_contract_content"] = criterion.tieu_chi_snapshot_json[
                "mandatory_contract_content"
            ]
            gate_values["template_field_unfilled"] = False
            if any(k in trigger and trigger[k] != v for k, v in gate_values.items()):
                continue
            verification = criterion.finding == "UNKNOWN"
            results.append(
                _risk(
                    request,
                    knowledge,
                    rule,
                    RiskSource(
                        yeu_cau_ca_id=criterion.yeu_cau_ca_id,
                        ket_qua_tieu_chi_id=criterion.ket_qua_id,
                    ),
                    criterion.uncertainty_reason or criterion.giai_thich,
                    [e.doan_id for e in criterion.evidence]
                    + [e.bang_chung_id for e in criterion.external_evidence],
                    criterion.legal_basis_ids,
                    "VERIFICATION" if verification else "COMPLIANCE",
                )
            )
    return results
