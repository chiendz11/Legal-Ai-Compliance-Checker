import json

import pytest

from devtools.parallel import SCENARIOS, json_text


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_retrieval_output_is_usable_by_reasoning(parallel_packs, knowledge, scenario):
    pack = parallel_packs[scenario]
    pack.validate_output(3, json.loads(json_text(pack.reference_output(3, knowledge))), knowledge)


@pytest.mark.parametrize("change", ["chunk", "criterion", "requirement", "run", "duplicate"])
def test_retrieval_owner_can_check_foreign_references(parallel_packs, knowledge, change):
    pack = parallel_packs["satisfied"]
    output = json.loads(json_text(pack.reference_output(3, knowledge)))
    if change == "duplicate":
        output.append(output[0])
    else:
        key = {
            "chunk": "doan_id",
            "criterion": "tieu_chi_id",
            "requirement": "yeu_cau_ca_id",
            "run": "lan_chay_id",
        }[change]
        output[0][key] = "FOREIGN"
    with pytest.raises(ValueError):
        pack.validate_output(3, output, knowledge)


def test_empty_retrieval_becomes_unknown_not_a_proven_violation(parallel_packs):
    handoffs = parallel_packs["insufficient_evidence"].handoffs
    assert handoffs.retrieval_output == []
    assert {r.finding for r in handoffs.compliance_output.criterion_results} == {"UNKNOWN"}
    assert handoffs.compliance_output.requirement_results[0].status == "INSUFFICIENT"
