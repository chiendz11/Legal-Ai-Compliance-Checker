"""Snapshot history, transaction safety and multi-run behavior in PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.assessments.repository import Store
from legal_checker.modules.legal_knowledge.repository import Knowledge


def test_concurrent_first_snapshot_is_idempotent(database_url):
    with ThreadPoolExecutor(max_workers=4) as executor:
        snapshots = list(executor.map(lambda _: Knowledge(database_url), range(4)))
    assert len({snapshot.sha256 for snapshot in snapshots}) == 1
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM knowledge.knowledge_snapshots"
            ).fetchone()["n"]
            == 1
        )


def test_source_change_creates_new_hash_and_old_snapshot_replays(database_url):
    first = Knowledge(database_url)
    with connect_postgres(database_url) as connection:
        connection.execute(
            "UPDATE knowledge.tieu_chi_danh_gia SET noi_dung='Changed' "
            "WHERE tieu_chi_id='TC_PV_GYC005_01'"
        )
    second = Knowledge(database_url)
    assert first.sha256 != second.sha256
    restored = Knowledge(database_url, first.sha256)
    assert restored.criteria == first.criteria
    assert restored.criteria["TC_PV_GYC005_01"]["human_verified"] is False
    with pytest.raises(psycopg.errors.RaiseException), connect_postgres(database_url) as connection:
        connection.execute(
            "UPDATE knowledge.knowledge_snapshots SET content=%s WHERE sha256=%s",
            ("{}", first.sha256),
        )


def test_run_retry_serialized_and_normalized_lineage(
    database_url, request_factory, response_factory
):
    snapshot = Knowledge(database_url)
    request = request_factory(finding="MISSING")
    assert request.knowledge_snapshot_sha256 == snapshot.sha256
    store = Store(database_url)
    with ThreadPoolExecutor(max_workers=2) as executor:
        outputs = list(
            executor.map(lambda _: store.save(request, response_factory(request)), range(2))
        )
    assert outputs[0] == outputs[1]
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM runtime.assessment_runs").fetchone()["n"]
            == 1
        )
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM runtime.assessment_output_lineage"
            ).fetchone()["n"]
            == 0
        )


def test_foreign_output_failure_rolls_back_case_and_run(
    database_url, request_factory, response_factory
):
    Knowledge(database_url)
    request = request_factory(finding="MISSING")
    response = response_factory(request)
    from legal_checker.shared.contracts.risk import RiskResult

    response.payload.risks.append(
        RiskResult(
            ket_qua_rui_ro_id="TRANSPORT_TEST_RISK",
            ca_id=request.ca_id,
            risk_type="COMPLIANCE",
            rui_ro_id="NO_CATALOG_ENTRY",
            severity="LOW",
            source={"ket_qua_tieu_chi_id": "NO_CRITERION"},
            quy_tac_id="NO_RULE",
            giai_thich="Invalid foreign-key fixture for rollback test",
            risk_snapshot={"ten_rui_ro": "Transport test", "mo_ta": "Invalid FK"},
            rule_snapshot_json={},
            evidence_ids=[],
            legal_basis_ids=[],
        )
    )
    with pytest.raises(ValueError, match="source C07 is outside current run"):
        Store(database_url).save(request, response)
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM runtime.assessment_runs").fetchone()["n"]
            == 0
        )
        assert (
            connection.execute("SELECT count(*) AS n FROM runtime.ca_danh_gia").fetchone()["n"] == 0
        )


def test_requirement_reason_order_does_not_conflict_across_runs(
    database_url, request_factory, response_factory
):
    from devtools.qa_runs import new_run
    from legal_checker.modules.legal_knowledge.repository import canonical

    Knowledge(database_url)
    original = request_factory()
    original.payload.requirements[0].reason = {"summary": "same reason", "source": "test"}
    store = Store(database_url)
    store.save(original, response_factory(original))
    second = new_run(original.model_dump(mode="json"), "SECOND_RUN")
    second.payload.requirements[0].reason = {"source": "test", "summary": "same reason"}
    store.save(second, response_factory(second))
    with connect_postgres(database_url) as connection:
        row = connection.execute("SELECT ly_do FROM runtime.yeu_cau_ap_dung").fetchone()
        assert row["ly_do"] == canonical(original.payload.requirements[0].reason)
        assert (
            connection.execute("SELECT count(*) AS n FROM runtime.assessment_runs").fetchone()["n"]
            == 2
        )
