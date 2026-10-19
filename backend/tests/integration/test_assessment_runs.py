"""Group D run lifecycle: API → queue → runner → workflow → C13 draft → versions/export.

Step implementations are synthetic fixtures (no legal quality is claimed); the tests cover
orchestration, persistence, idempotency, failure recording and report/run scoping.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import psycopg
import pytest
from fastapi.testclient import TestClient
from legal_checker.api.dependencies import Services
from legal_checker.core.config import Settings
from legal_checker.core.exceptions import ConflictError
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.assessments.cases import CaseRepository
from legal_checker.modules.assessments.runs import RunRepository
from legal_checker.modules.assessments.service import AssessmentService
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.modules.reports.repository import PostgresReportStore
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.document_intelligence import (
    ContractProfile,
    DocumentIntelligenceResult,
)
from legal_checker.shared.contracts.pipeline import PipelineResponse, PipelineResult
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.workflows.assessment_workflow import DraftModules
from legal_checker.workflows.runner import (
    AssessmentRunner,
    TransientRunError,
    UnconfiguredModules,
)
from legal_checker.workflows.states import STAGES

CASE = "CA_TEST"


def register_case(database_url):
    with connect_postgres(database_url) as connection:
        connection.execute(
            "INSERT INTO knowledge.phien_ban_trien_khai (phien_ban_id) VALUES ('DEPLOY_TEST') "
            "ON CONFLICT DO NOTHING"
        )
        connection.execute(
            "INSERT INTO runtime.hop_dong (hop_dong_id, tep_nguon_id) VALUES ('HD_TEST', 'TEP')"
        )
        connection.execute(
            """INSERT INTO runtime.tep_nguon (tep_id, hop_dong_id, object_uri, mime_type, sha256)
               VALUES ('TEP', 'HD_TEST', 'fixture://contract.pdf', 'application/pdf', %s)""",
            ("a" * 64,),
        )
        connection.execute(
            """INSERT INTO runtime.ca_danh_gia
               (ca_id, hop_dong_id, ngay_danh_gia, phien_ban_id, rule_version,
                legal_knowledge_version, tenant_id, created_by)
               VALUES (%s, 'HD_TEST', '2026-10-12', 'DEPLOY_TEST', 'RULE_TEST', 'LEGAL_TEST',
                       'TENANT_TEST', 'USER_TEST')""",
            (CASE,),
        )


class FixtureSource:
    """Synthetic step adapters; `fail_with` injects one failure on the next prepare()."""

    name = "TEST_FIXTURE"

    def __init__(self, request_factory):
        self.request_factory = request_factory
        self.fail_with = None
        self.foreign_profile = False

    def prepare(self, context):
        if self.fail_with:
            error, self.fail_with = self.fail_with, None
            raise error

        def bind(data):
            data.update(ca_id=context.ca_id, run_id=context.run_id, trace_id=context.trace_id)

        request = self.request_factory(mutate=bind)
        case = AssessmentCase(
            ca_id=context.ca_id,
            hop_dong_id="HD_TEST",
            source={
                "tep_id": "TEP",
                "object_uri": "fixture://contract.pdf",
                "mime_type": "application/pdf",
                "sha256": "a" * 64,
            },
            assessment_context={"ngay_danh_gia": "2026-10-12"},
            deployment={
                k: getattr(context, k)
                for k in ("phien_ban_id", "rule_version", "legal_knowledge_version")
            },
            tenant_id="TENANT_TEST",
            created_by="USER_TEST",
        )
        profile_owner = "FOREIGN" if self.foreign_profile else case.hop_dong_id
        document = DocumentIntelligenceResult(
            contract_profile=ContractProfile(hop_dong_id=profile_owner, profile={}),
            chunks=request.payload.chunks,
            citations=[],
        )
        scopes = [
            ScopeResolution(
                yeu_cau_ca_id=r.yeu_cau_ca_id,
                ca_id=r.ca_id,
                requirement_id=r.requirement_id,
                scope_status=r.scope_status,
                scope_reason="Fixture scope",
            )
            for r in request.payload.requirements
        ]
        modules = DraftModules(
            intake=SimpleNamespace(register=lambda item: item),
            documents=SimpleNamespace(extract=lambda item: document),
            scope=SimpleNamespace(resolve=lambda *args: scopes),
            temporal=SimpleNamespace(resolve=lambda *args: request.payload.requirements),
            retrieval=SimpleNamespace(retrieve=lambda *args: request.payload.retrieval),
            citations=SimpleNamespace(validate=lambda *args: []),
            observations=SimpleNamespace(observe=lambda *args: request.payload.observations),
        )

        def evaluator(pipeline_request, knowledge):
            # Transport-only response: orchestration is under test, not legal reasoning.
            return PipelineResponse(
                **pipeline_request.model_dump(exclude={"contract_name", "payload"}),
                produced_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                payload=PipelineResult(
                    criterion_results=[],
                    requirement_results=[],
                    risks=[],
                    recommendations=[],
                    excluded_requirements=[],
                ),
            )

        return case, modules, evaluator


class SyncQueue:
    def __init__(self):
        self.runner = None
        self.enqueued = []

    def enqueue(self, ca_id, run_id):
        self.enqueued.append((ca_id, run_id))
        if self.runner:
            self.runner.execute(ca_id, run_id)


@pytest.fixture
def env(database_url, request_factory, tmp_path):
    register_case(database_url)
    knowledge = Knowledge(database_url)
    runs = RunRepository(database_url)
    reports = PostgresReportStore(database_url)
    source = FixtureSource(request_factory)
    queue = SyncQueue()
    runner = AssessmentRunner(runs=runs, reports=reports, knowledge=knowledge, source=source)
    queue.runner = runner
    cases = CaseRepository(database_url)
    service = AssessmentService(
        cases=cases,
        runs=runs,
        reports=reports,
        knowledge=knowledge,
        queue=queue,
        module_source=source.name,
    )
    settings = replace(
        Settings.from_env(), database_url=database_url, report_export_dir=tmp_path / "exports"
    )
    services = Services(
        knowledge=knowledge,
        assessments=None,
        settings=settings,
        cases=cases,
        reports=reports,
        runner=runner,
        assessment_service=service,
    )
    from legal_checker.main import create_app

    client = TestClient(create_app(settings=settings, services=services))
    return SimpleNamespace(
        client=client,
        runs=runs,
        reports=reports,
        runner=runner,
        source=source,
        queue=queue,
        service=service,
        database_url=database_url,
    )


def start(client, key="key-1"):
    response = client.post(f"/api/v1/cases/{CASE}/runs", headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    return response.json()


def test_run_completes_with_progress_results_and_one_report(env):
    accepted = start(env.client)
    run_id = accepted["context"]["run_id"]
    assert accepted["status"] == "QUEUED"
    assert accepted["status_url"] == f"/api/v1/cases/{CASE}/runs/{run_id}/status"

    status = env.client.get(accepted["status_url"]).json()
    assert status["status"] == "COMPLETED" and status["error"] is None
    assert [s["stage"] for s in status["stages"]] == list(STAGES)
    assert all(s["status"] == "COMPLETED" and s["finished_at"] for s in status["stages"])

    results = env.client.get(accepted["results_url"])
    assert results.status_code == 200
    assert results.json()["context"]["run_id"] == run_id

    listing = env.client.get(f"/api/v1/cases/{CASE}/runs/{run_id}/reports").json()
    assert listing["total"] == 1
    report = listing["items"][0]["report"]
    assert report["report_status"] == "DRAFT" and report["review_status"] == "PENDING"
    assert report["report_json"]["audit"]["module_source"] == "TEST_FIXTURE"
    assert report["report_json"]["audit"]["context"]["run_id"] == run_id

    again = env.client.get(f"/api/v1/reports/{report['bao_cao_id']}").json()
    assert again["report"] == report and again["run_id"] == run_id

    rebuilt = env.client.post(f"/api/v1/cases/{CASE}/runs/{run_id}/reports")
    assert rebuilt.status_code == 201
    assert rebuilt.json()["report"]["bao_cao_id"] == report["bao_cao_id"]
    assert env.client.get(f"/api/v1/cases/{CASE}/runs/{run_id}/reports").json()["total"] == 1

    case = env.client.get(f"/api/v1/cases/{CASE}").json()
    assert case["latest_run_id"] == run_id and case["latest_run_status"] == "COMPLETED"
    assert case["case"]["deployment"]["rule_version"] == "RULE_TEST"


def test_same_idempotency_key_returns_original_run_without_rerunning(env):
    first = start(env.client, "same")
    second = start(env.client, "same")
    assert first["context"] == second["context"]
    other = start(env.client, "different")
    assert other["context"]["run_id"] != first["context"]["run_id"]
    status = env.runs.get(CASE, first["context"]["run_id"])
    assert status.attempts == 1


def test_unconfigured_modules_fail_clearly_without_report(env):
    env.runner.source = UnconfiguredModules()
    accepted = start(env.client)
    status = env.client.get(accepted["status_url"]).json()
    assert status["status"] == "FAILED"
    assert status["error"]["code"] == "PROCESSING_FAILED"
    assert status["error"]["details"] == [{"reason": "MODULE_NOT_IMPLEMENTED"}]
    assert status["error"]["trace_id"] == accepted["context"]["trace_id"]
    results = env.client.get(accepted["results_url"])
    assert results.status_code == 409
    assert results.json()["error"]["code"] == "RESULT_NOT_READY"
    run_id = accepted["context"]["run_id"]
    assert env.client.get(f"/api/v1/cases/{CASE}/runs/{run_id}/reports").json()["total"] == 0
    rebuild = env.client.post(f"/api/v1/cases/{CASE}/runs/{run_id}/reports")
    assert rebuild.status_code == 409


def test_handoff_violation_marks_the_failing_stage(env):
    env.source.foreign_profile = True
    status = env.client.get(start(env.client)["status_url"]).json()
    stages = {s["stage"]: s["status"] for s in status["stages"]}
    assert status["status"] == "FAILED"
    assert status["error"]["details"] == [{"reason": "HANDOFF_VALIDATION_FAILED"}]
    assert stages["INTAKE"] == "COMPLETED"
    assert stages["DOCUMENT_INTELLIGENCE"] == "FAILED"
    assert stages["SCOPE_RESOLUTION"] == "PENDING"


def test_transient_failure_releases_run_and_retry_completes(env):
    env.queue.runner = None  # accept only; execute manually
    accepted = start(env.client)
    run_id = accepted["context"]["run_id"]
    env.source.fail_with = psycopg.OperationalError("database restarting")
    with pytest.raises(TransientRunError):
        env.runner.execute(CASE, run_id)
    assert env.runs.get(CASE, run_id).status == "QUEUED"
    assert env.runner.execute(CASE, run_id).status == "COMPLETED"
    assert env.runs.get(CASE, run_id).attempts == 2


def test_claim_is_exclusive_and_expired_lease_is_recoverable(env):
    env.queue.runner = None
    run_id = start(env.client)["context"]["run_id"]
    assert env.runs.claim(CASE, run_id, timedelta(minutes=10)).status == "RUNNING"
    assert env.runs.claim(CASE, run_id, timedelta(minutes=10)) is None
    assert env.runs.recoverable(timedelta(minutes=5), timedelta(minutes=10)) == []
    assert env.runs.recoverable(timedelta(minutes=5), timedelta(0)) == [(CASE, run_id)]
    assert env.runs.claim(CASE, run_id, timedelta(0)).attempts == 2


def test_lost_enqueue_is_recovered_once_queued_long_enough(env):
    env.queue.runner = None
    run_id = start(env.client)["context"]["run_id"]
    env.queue.enqueued.clear()
    assert env.service.recover(timedelta(minutes=5), timedelta(minutes=10)) == []
    assert env.service.recover(timedelta(0), timedelta(minutes=10)) == [(CASE, run_id)]
    assert env.queue.enqueued == [(CASE, run_id)]


def test_report_versions_are_immutable_and_scoped_to_their_run(env):
    accepted = start(env.client)
    run_id = accepted["context"]["run_id"]
    stored = env.reports.list_for_run(CASE, run_id, offset=0, limit=10)[0][0]
    assert env.reports.save_version(run_id, stored.report).version_no == 1
    changed = stored.report.model_copy(update={"review_status": "CHANGED"})
    with pytest.raises(ConflictError):
        env.reports.save_version(run_id, changed)
    with connect_postgres(env.database_url) as connection:
        with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
            connection.execute(
                "UPDATE runtime.report_versions SET report_json='{}'::jsonb WHERE bao_cao_id=%s",
                (stored.report.bao_cao_id,),
            )
    other = start(env.client, "other")["context"]["run_id"]
    other_reports, _ = env.reports.list_for_run(CASE, other, offset=0, limit=10)
    assert [r.run_id for r in other_reports] == [other]
    assert other_reports[0].report.bao_cao_id != stored.report.bao_cao_id


def test_errors_use_the_documented_envelope(env):
    missing = ("/api/v1/cases/NOPE", "/api/v1/reports/NOPE", f"/api/v1/cases/{CASE}/runs/X/status")
    for url in missing:
        response = env.client.get(url)
        assert response.status_code == 404
        error = response.json()["error"]
        assert error["code"] == "NOT_FOUND" and error["trace_id"] and error["message"]
    missing_case = env.client.post("/api/v1/cases/NOPE/runs", headers={"Idempotency-Key": "k"})
    assert missing_case.status_code == 404
    assert env.client.post(f"/api/v1/cases/{CASE}/runs").status_code == 422


def test_case_listing_pages_registered_cases(env):
    page = env.client.get("/api/v1/cases", params={"page": 1, "page_size": 1}).json()
    assert page["total"] == 1 and page["page_size"] == 1
    assert page["items"][0]["case"]["source"]["tep_id"] == "TEP"
    assert page["items"][0]["latest_run_id"] is None
    assert env.client.get("/api/v1/cases", params={"page_size": 101}).status_code == 422


def test_export_returns_the_exact_version_and_records_it(env):
    accepted = start(env.client)
    run_id = accepted["context"]["run_id"]
    report_id = env.client.get(f"/api/v1/cases/{CASE}/runs/{run_id}/reports").json()["items"][0][
        "report"
    ]["bao_cao_id"]
    docx = env.client.get(f"/api/v1/reports/{report_id}/export", params={"format": "docx"})
    assert docx.status_code == 200
    assert docx.content[:2] == b"PK"
    assert report_id in docx.headers["content-disposition"]
    assert "docx" in env.reports.get(report_id).exports
    assert env.client.get(f"/api/v1/reports/{report_id}/export?format=html").status_code == 422
