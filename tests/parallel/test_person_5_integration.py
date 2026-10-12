import json
from dataclasses import replace

import pytest

from app.workflows.handoffs import report_input_from_draft
from app.workflows.pipelines.draft_assessment import DraftAssessmentWorkflow
from devtools.parallel import SCENARIOS, json_text
from devtools.replay import fixture_modules


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_report_can_be_built_without_ocr_search_or_llm(parallel_packs, knowledge, scenario):
    pack = parallel_packs[scenario]
    output = pack.reference_output(5, knowledge)
    assert output == pack.handoffs.report_output
    assert output.report_status == "DRAFT"
    assert output.review_status == "PENDING"
    pack.validate_output(5, json.loads(json_text(output)), knowledge)


def test_draft_workflow_preserves_c09_for_the_report_builder(parallel_packs, knowledge):
    handoffs = parallel_packs["stale_citation"].handoffs
    draft = DraftAssessmentWorkflow(fixture_modules(handoffs), knowledge).evaluate(
        handoffs.document_input.case, handoffs.document_input.context
    )
    assert draft.citation_findings == handoffs.legal_output.citations
    assert report_input_from_draft(draft) == handoffs.integration_input


def test_replace_one_real_module_slot_while_other_owners_use_fixtures(parallel_packs, knowledge):
    handoffs = parallel_packs["satisfied"].handoffs

    class EmptyRetrieval:
        calls = 0

        def retrieve(self, context, requirements, chunks, snapshot):
            self.calls += 1
            assert snapshot.sha256 == context.knowledge_snapshot_sha256
            assert requirements and chunks
            return []

    retrieval = EmptyRetrieval()
    modules = replace(fixture_modules(handoffs), retrieval=retrieval)
    draft = DraftAssessmentWorkflow(modules, knowledge).evaluate(
        handoffs.document_input.case, handoffs.document_input.context
    )
    assert retrieval.calls == 1
    assert draft.retrieval == []
    assert {result.finding for result in draft.evaluation.payload.criterion_results} == {"UNKNOWN"}
    assert draft.evaluation.payload.requirement_results[0].status == "INSUFFICIENT"


@pytest.mark.parametrize(
    "change", ["citation_section", "drop_risk", "run", "publish", "findings", "evidence"]
)
def test_report_preserves_both_branches_and_pending_review(parallel_packs, knowledge, change):
    pack = parallel_packs["stale_citation"]
    output = json.loads(json_text(pack.reference_output(5, knowledge)))
    content = output["report_json"]
    if change == "citation_section":
        content["risks"]["compliance"] = content["risks"]["citation"]
        content["risks"]["citation"] = []
    elif change == "drop_risk":
        content["risks"]["citation"].clear()
    elif change == "run":
        content["audit"]["context"]["run_id"] = "FOREIGN_RUN"
    elif change == "publish":
        output["report_status"] = "PUBLISHED"
    elif change == "findings":
        content["compliance"]["requirement_results"][0]["status"] = "NON_COMPLIANT"
    else:
        content["compliance"]["evidence"].clear()
    with pytest.raises(ValueError):
        pack.validate_output(5, output, knowledge)
