import json

import pytest

from devtools.parallel import SCENARIOS, json_text


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_compliance_runs_real_engines_without_upstream_services(
    parallel_packs, knowledge, scenario
):
    pack = parallel_packs[scenario]
    output = pack.reference_output(4, knowledge)
    assert output == pack.handoffs.compliance_output
    pack.validate_output(4, json.loads(json_text(output)), knowledge)


@pytest.mark.parametrize("change", ["quote", "aggregate", "context", "risk", "recommendation"])
def test_compliance_owner_can_validate_output_provenance(parallel_packs, knowledge, change):
    pack = parallel_packs["violated"]
    output = json.loads(json_text(pack.reference_output(4, knowledge)))
    if change == "quote":
        output["criterion_results"][0]["evidence"][0]["trich_dan"] = "Fabricated quote"
    elif change == "aggregate":
        output["requirement_results"][0]["status"] = "COMPLIANT"
    elif change == "context":
        output["context"]["run_id"] = "FOREIGN_RUN"
    elif change == "risk":
        output["risks"][0]["severity"] = "CRITICAL"
    else:
        output["recommendations"].clear()
    with pytest.raises(ValueError):
        pack.validate_output(4, output, knowledge)


def test_person_four_cannot_generate_citation_warnings(parallel_packs, knowledge):
    pack = parallel_packs["stale_citation"]
    output = json.loads(json_text(pack.reference_output(4, knowledge)))
    assert output["risks"] == []
    output["risks"] = pack.handoffs.pipeline_output.payload.model_dump(mode="json")["risks"]
    with pytest.raises(ValueError, match="citation-branch"):
        pack.validate_output(4, output, knowledge)
