"""Oracle check on the private DEV_VALIDATION dataset: workflow + report builder reproduce the
frozen QA C13 for the reference run. Needs a seeded DB, so it only runs when
REFERENCE_DATABASE_URL points at one (CI has no private dataset)."""

import os
from collections import Counter

import pytest
from devtools.qa_validation import join_artifacts
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.modules.reports.service import build_run_report
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.report import FinalReport
from legal_checker.workflows.assessment_workflow import DraftAssessmentWorkflow
from legal_checker.workflows.reference import MODULE_SOURCE, ReferenceReplay

DATABASE_URL = os.environ.get("REFERENCE_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="Set REFERENCE_DATABASE_URL")
CASES = os.environ.get("REFERENCE_CASES", "CA360_001,CA360_051").split(",")


@pytest.fixture(scope="module")
def knowledge():
    return Knowledge(DATABASE_URL)


def expected_report(ca_id):
    with connect_postgres(DATABASE_URL) as connection:
        rows = connection.execute(
            "SELECT * FROM qa.artifacts WHERE case_id=%s AND role='EXPECTED' "
            "AND contract_name='C13'",
            (ca_id,),
        ).fetchall()
    return FinalReport.model_validate(next(iter(join_artifacts(rows).values())))


def replay(knowledge, ca_id, context=None):
    reference = ReferenceReplay.load(DATABASE_URL, ca_id)
    context = context or reference.reference_context
    modules, evaluator = reference.build(context)
    draft = DraftAssessmentWorkflow(modules, knowledge, evaluator=evaluator).evaluate(
        reference.case, context
    )
    return build_run_report(draft, knowledge, MODULE_SOURCE)


def without_source(report: FinalReport) -> dict:
    data = report.model_dump(mode="json")
    assert data["report_json"]["audit"].pop("module_source") == MODULE_SOURCE
    return data


@pytest.mark.parametrize("ca_id", CASES)
def test_reference_run_reproduces_frozen_c13(knowledge, ca_id):
    assert without_source(replay(knowledge, ca_id)) == expected_report(ca_id).model_dump(
        mode="json"
    )


@pytest.mark.parametrize("ca_id", CASES)
def test_new_run_id_keeps_every_finding_and_rebinds_run_ownership(knowledge, ca_id):
    reference = ReferenceReplay.load(DATABASE_URL, ca_id).reference_context
    context = Context(**{**reference.model_dump(), "run_id": "RUN_REPLAY", "trace_id": "TRACE"})
    report = replay(knowledge, ca_id, context).report_json
    expected = expected_report(ca_id).report_json
    assert report.audit["context"]["run_id"] == "RUN_REPLAY"
    assert {c.lan_chay_id for c in report.compliance.criterion_results} <= {"RUN_REPLAY"}
    assert {f.lan_chay_id for f in report.citation_validation.findings} <= {"RUN_REPLAY"}
    assert Counter(r.status for r in report.compliance.requirement_results) == Counter(
        r.status for r in expected.compliance.requirement_results
    )
    assert [c.ket_qua_id for c in report.compliance.criterion_results] == [
        c.ket_qua_id for c in expected.compliance.criterion_results
    ]
    assert report.risks == expected.risks and report.recommendations == expected.recommendations
