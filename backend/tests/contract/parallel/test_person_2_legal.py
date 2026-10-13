import json

import pytest
from devtools.parallel import SCENARIOS, json_text, pipeline_request
from legal_checker.shared.contracts.handoffs import ScopeInput
from legal_checker.workflows.handoffs import validate_legal
from legal_checker.workflows.steps_5_7 import evaluate
from pydantic import ValidationError


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_legal_outputs_are_valid_with_fixture_document_input(parallel_packs, knowledge, scenario):
    pack = parallel_packs[scenario]
    pack.validate_output(2, json.loads(json_text(pack.reference_output(2, knowledge))), knowledge)


@pytest.mark.parametrize(
    "change",
    [
        "scope",
        "version",
        "pin",
        "citation",
        "missing_citation",
        "provenance",
        "family",
        "replacement",
    ],
)
def test_legal_contract_rejects_changed_scope_and_foreign_citations(
    parallel_packs, knowledge, change
):
    pack = parallel_packs["satisfied"]
    output = pack.handoffs.legal_output.model_copy(deep=True)
    if change == "scope":
        output.scope[0].scope_status = "NO_MATCH"
    elif change == "version":
        output.requirements[0].requirement_version_id = "FOREIGN_VERSION"
    elif change == "pin":
        output.requirements[0].phien_ban_id = "FOREIGN_DEPLOYMENT"
    elif change == "citation":
        output.citations[0].vien_dan_id = "UNEXTRACTED"
    elif change == "missing_citation":
        output.citations.clear()
    elif change == "provenance":
        output.requirements[0].profile_snapshot_json.clear()
    elif change == "family":
        output.scope[0].requirement_id = "FOREIGN_FAMILY"
        output.requirements[0].requirement_id = "FOREIGN_FAMILY"
        output.requirements[0].requirement_version_id = None
        output.requirements[0].version_status = "UNKNOWN"
        output.requirements[0].applicability_status = "UNKNOWN"
    else:
        output.citations[0].replacement_van_ban_id = "FOREIGN_DOCUMENT"
    with pytest.raises(ValueError):
        validate_legal(
            pack.handoffs.document_input.context, pack.handoffs.document_output, output, knowledge
        )


def test_applicable_law_input_cannot_receive_citations(parallel_packs):
    data = parallel_packs["satisfied"].handoffs.scope_input.model_dump(mode="json")
    data["citations"] = []
    with pytest.raises(ValidationError, match="Extra inputs"):
        ScopeInput.model_validate(data)


def test_stale_citation_does_not_change_compliance_selection_or_findings(parallel_packs, knowledge):
    request = pipeline_request(parallel_packs["stale_citation"].handoffs)
    stale = evaluate(request, knowledge)
    request.payload.citations[0].status = "VALID"
    assert parallel_packs["stale_citation"].handoffs.legal_output.citations[0].status == "STALE"
    valid = evaluate(request, knowledge)
    assert stale.payload.criterion_results == valid.payload.criterion_results
    assert stale.payload.requirement_results == valid.payload.requirement_results
    assert valid.payload.requirement_results[0].status == "COMPLIANT"
    assert not valid.payload.risks
    assert len(stale.payload.risks) == 1
    assert stale.payload.risks[0].risk_type == "CITATION"
