"""Generated steps 5–7 outputs survive SQL with exact immutable run membership."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from devtools.qa_runs import new_run
from legal_checker.core.exceptions import ConflictError
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.assessments.repository import OUTPUTS, Store
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.workflows.steps_5_7 import evaluate
from psycopg.types.json import Jsonb


@pytest.fixture
def generated(database_url, request_factory):
    knowledge = Knowledge(database_url)
    request = request_factory()
    # Missing observations are genuine uncertainty; no reference C07/C08/C10/C11 is read.
    request.payload.observations.clear()
    response = evaluate(request, knowledge)
    assert response.payload.criterion_results
    assert response.payload.requirement_results
    assert response.payload.risks
    assert response.payload.recommendations
    return Store(database_url), request, response, knowledge


def test_generated_pipeline_save_read_normalized_and_full_lineage(generated, database_url):
    store, request, response, _ = generated
    assert store.save(request, response) == response
    assert store.get(request.ca_id, request.run_id) == response
    assert store.get_input(request.ca_id, request.run_id) == request
    lineage = store.get_lineage(request.ca_id, request.run_id)
    assert len(lineage) == sum(len(getattr(response.payload, attr)) for attr, _ in OUTPUTS.values())
    assert {row["table_name"] for row in lineage} == set(OUTPUTS)
    assert all(row["run_id"] == request.run_id for row in lineage)
    assert store.get_lineage(request.ca_id, "ABSENT") == []
    assert store.get_input(request.ca_id, "ABSENT") is None
    with connect_postgres(database_url) as connection:
        for table, (attr, _) in OUTPUTS.items():
            assert connection.execute(f"SELECT count(*) AS n FROM runtime.{table}").fetchone()[
                "n"
            ] == len(getattr(response.payload, attr))
        normalized = connection.execute(
            "SELECT nguon_tieu_chi_id FROM runtime.ket_qua_rui_ro"
        ).fetchall()
        assert {row["nguon_tieu_chi_id"] for row in normalized} <= {
            row.ket_qua_id for row in response.payload.criterion_results
        }


def test_generated_run_retry_conflict_and_history(generated, database_url):
    store, request, response, knowledge = generated
    with ThreadPoolExecutor(max_workers=2) as pool:
        saved = list(pool.map(lambda _: store.save(request, response), range(2)))
    assert saved == [response, response]
    changed = request.model_copy(deep=True)
    changed.trace_id = "DIFFERENT_INPUT"
    with pytest.raises(ConflictError, match="different input"):
        store.save(changed, evaluate(changed, knowledge))
    second = new_run(request.model_dump(mode="json"), "SECOND_GENERATED_RUN")
    second_response = evaluate(second, knowledge)
    store.save(second, second_response)
    first_ids = {row["output_id"] for row in store.get_lineage(request.ca_id, request.run_id)}
    second_ids = {row["output_id"] for row in store.get_lineage(second.ca_id, second.run_id)}
    assert first_ids.isdisjoint(second_ids)
    assert store.get(request.ca_id, request.run_id) == response
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM runtime.assessment_runs").fetchone()["n"]
            == 2
        )


@pytest.mark.parametrize(
    "target",
    [
        "criterion_run",
        "criterion_snapshot",
        "criterion_quote",
        "requirement",
        "risk",
        "recommendation",
    ],
)
def test_foreign_output_graph_is_rejected_without_writes(generated, database_url, target):
    store, request, response, _ = generated
    if target == "criterion_run":
        response.payload.criterion_results[0].lan_chay_id = "ANOTHER_RUN"
    elif target == "criterion_snapshot":
        response.payload.criterion_results[0].tieu_chi_snapshot_json[
            "knowledge_snapshot_sha256"
        ] = "0" * 64
    elif target == "criterion_quote":
        response.payload.criterion_results[0].evidence = [
            request.payload.chunks[0].model_dump(include=set())
        ]
        # Build a structurally valid but ungrounded output quote.
        from legal_checker.shared.contracts.document_intelligence import Evidence

        response.payload.criterion_results[0].evidence = [
            Evidence(doan_id="D_TEST", trich_dan="Invented", ky_tu_bat_dau=0, ky_tu_ket_thuc=8)
        ]
    elif target == "requirement":
        response.payload.requirement_results[0].yeu_cau_ca_id = "ANOTHER_REQUIREMENT"
    elif target == "risk":
        response.payload.risks[0].source.ket_qua_tieu_chi_id = "ANOTHER_RUN_FINDING"
    else:
        response.payload.recommendations[0].ket_qua_rui_ro_id = "ANOTHER_RUN_RISK"
    with pytest.raises(ValueError):
        store.save(request, response)
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM runtime.assessment_runs").fetchone()["n"]
            == 0
        )


def test_transaction_rolls_back_after_normalized_outputs_and_can_retry(
    generated, database_url, monkeypatch
):
    store, request, response, _ = generated
    original = store.save_outputs

    def fail_after_write(connection, request, response):
        original(connection, request, response)
        raise RuntimeError("Injected failure after output and lineage writes")

    monkeypatch.setattr(store, "save_outputs", fail_after_write)
    with pytest.raises(RuntimeError, match="Injected failure"):
        store.save(request, response)
    with connect_postgres(database_url) as connection:
        for table in (
            *OUTPUTS,
            "assessment_runs",
            "assessment_output_lineage",
            "assessment_case_pins",
            "ca_danh_gia",
        ):
            assert (
                connection.execute(f"SELECT count(*) AS n FROM runtime.{table}").fetchone()["n"]
                == 0
            )
    monkeypatch.setattr(store, "save_outputs", original)
    assert store.save(request, response) == response


def test_seed_style_plain_reason_preserved_when_reusing_requirement(
    database_url, request_factory, response_factory
):
    Knowledge(database_url)
    request = request_factory()
    request.payload.requirements[0].reason = {"summary": "Seed plain text reason"}
    store = Store(database_url)
    store.save(request, response_factory(request))
    with connect_postgres(database_url) as connection:
        connection.execute(
            "UPDATE runtime.yeu_cau_ap_dung SET ly_do=%s", ("Seed plain text reason",)
        )
    second = new_run(request.model_dump(mode="json"), "PLAIN_REASON_SECOND")
    store.save(second, response_factory(second))
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute("SELECT ly_do FROM runtime.yeu_cau_ap_dung").fetchone()["ly_do"]
            == "Seed plain text reason"
        )


@pytest.mark.parametrize("target", ["input", "output", "lineage"])
def test_checksum_and_lineage_corruption_detected(generated, database_url, target):
    store, request, response, _ = generated
    store.save(request, response)
    with connect_postgres(database_url) as connection:
        if target == "lineage":
            connection.execute("UPDATE runtime.assessment_output_lineage SET payload='{}'::jsonb")
        else:
            column = "input_json" if target == "input" else "response_json"
            connection.execute(
                f"UPDATE runtime.assessment_runs SET {column} = {column} || %s",
                (Jsonb({"trace_id": "TAMPERED"}),),
            )
    read = (
        store.get_input
        if target == "input"
        else store.get
        if target == "output"
        else store.get_lineage
    )
    with pytest.raises(ValueError, match="checksum|lineage"):
        read(request.ca_id, request.run_id)
    if target != "lineage":
        with pytest.raises(ValueError, match="checksum"):
            store.save(request, response)


def test_legacy_snapshot_checksum_checked_before_new_optional_defaults(
    database_url, request_factory, response_factory
):
    Knowledge(database_url)
    request = request_factory()
    response = response_factory(request)
    store = Store(database_url)
    store.save(request, response)
    input_json = request.model_dump(mode="json")
    input_json["payload"].pop("external_evidence_registry")
    input_json["payload"].pop("citation_branch_status")
    output_json = response.model_dump(mode="json")
    output_json["payload"].pop("diagnostics")

    def checksum(value):
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    with connect_postgres(database_url) as connection:
        connection.execute(
            "UPDATE runtime.assessment_runs SET input_json=%s, input_sha256=%s, "
            "response_json=%s, output_sha256=%s",
            (Jsonb(input_json), checksum(input_json), Jsonb(output_json), checksum(output_json)),
        )
    assert store.get(request.ca_id, request.run_id) == response
    assert store.get_input(request.ca_id, request.run_id) == request
    assert store.save(request, response) == response


@pytest.mark.parametrize(
    "table,column,value",
    [
        ("ket_qua_tieu_chi", "giai_thich", "Tampered criterion"),
        ("ket_qua_tuan_thu", "giai_thich", "Tampered aggregation"),
        ("ket_qua_rui_ro", "severity_snapshot", "CRITICAL"),
        ("khuyen_nghi_danh_gia", "noi_dung_snapshot", "Tampered recommendation"),
        ("doan_hop_dong", "noi_dung", "Tampered original contract text"),
        ("ket_qua_truy_xuat", "duoc_chon", False),
        ("yeu_cau_ap_dung", "ly_do", "Tampered requirement reason"),
    ],
)
def test_all_read_paths_and_retry_detect_normalized_corruption(
    generated, database_url, table, column, value
):
    from psycopg import sql

    store, request, response, _ = generated
    store.save(request, response)
    with connect_postgres(database_url) as connection:
        connection.execute(
            sql.SQL("UPDATE {} SET {}=%s").format(
                sql.Identifier("runtime", table), sql.Identifier(column)
            ),
            (value,),
        )
    for read in (store.get, store.get_input, store.get_lineage):
        with pytest.raises(ValueError, match="normalized"):
            read(request.ca_id, request.run_id)
    with pytest.raises(ValueError, match="normalized"):
        store.save(request, response)


@pytest.mark.parametrize("mutation", ["delete", "extra", "change"])
def test_every_reader_and_retry_checks_exact_output_lineage(generated, database_url, mutation):
    store, request, response, _ = generated
    store.save(request, response)
    with connect_postgres(database_url) as connection:
        if mutation == "delete":
            connection.execute("DELETE FROM runtime.assessment_output_lineage")
        elif mutation == "extra":
            connection.execute(
                "INSERT INTO runtime.assessment_output_lineage VALUES (%s,%s,%s,%s,%s)",
                ("unknown_table", "EXTRA_OUTPUT", request.ca_id, request.run_id, Jsonb({})),
            )
        else:
            connection.execute("UPDATE runtime.assessment_output_lineage SET payload='{}'::jsonb")
    for read in (store.get, store.get_input, store.get_lineage):
        with pytest.raises(ValueError, match="lineage"):
            read(request.ca_id, request.run_id)
    with pytest.raises(ValueError, match="lineage"):
        store.save(request, response)


@pytest.mark.parametrize("field", ["ca_id", "run_id"])
def test_rehashed_foreign_snapshot_cannot_change_lookup_membership(generated, database_url, field):
    store, request, response, _ = generated
    store.save(request, response)
    foreign = request.model_dump(mode="json")
    foreign[field] = "OTHER_IDENTITY"
    checksum = hashlib.sha256(
        json.dumps(foreign, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    with connect_postgres(database_url) as connection:
        connection.execute(
            "UPDATE runtime.assessment_runs SET input_json=%s, input_sha256=%s",
            (Jsonb(foreign), checksum),
        )
    for read in (store.get, store.get_input, store.get_lineage):
        with pytest.raises(ValueError, match="membership"):
            read(request.ca_id, request.run_id)


def test_saved_graph_is_read_without_any_engine_recomputation(generated, monkeypatch):
    store, request, response, _ = generated
    store.save(request, response)

    def must_not_run(*args, **kwargs):
        pytest.fail("Reading a historical run must never recompute engines")

    for target in (
        "legal_checker.modules.compliance.criterion_reasoner.reason",
        "legal_checker.modules.compliance.requirement_aggregator.aggregate",
        "legal_checker.modules.risks.service.evaluate_risks",
        "legal_checker.modules.recommendations.service.generate_recommendations",
        "legal_checker.workflows.steps_5_7.evaluate",
    ):
        monkeypatch.setattr(target, must_not_run)
    assert store.get(request.ca_id, request.run_id) == response
    assert store.get_input(request.ca_id, request.run_id) == request
    assert store.get_lineage(request.ca_id, request.run_id)


def test_concurrent_different_input_has_one_winner_without_duplicate_outputs(
    generated, database_url
):
    store, request, response, knowledge = generated
    different = request.model_copy(deep=True)
    different.trace_id = "CONCURRENT_DIFFERENT_INPUT"
    second_response = evaluate(different, knowledge)

    def attempt(pair):
        candidate, output = pair
        try:
            return store.save(candidate, output)
        except ConflictError:
            return "CONFLICT"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, [(request, response), (different, second_response)]))
    assert outcomes.count("CONFLICT") == 1
    winner = next(result for result in outcomes if result != "CONFLICT")
    assert store.get(request.ca_id, request.run_id) == winner
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM runtime.assessment_runs").fetchone()["n"]
            == 1
        )
        for table, (attribute, _) in OUTPUTS.items():
            assert connection.execute(f"SELECT count(*) AS n FROM runtime.{table}").fetchone()[
                "n"
            ] == len(getattr(winner.payload, attribute))


def test_other_case_never_reads_a_run_with_the_same_run_id(generated):
    store, request, response, _ = generated
    store.save(request, response)
    assert store.get("ANOTHER_CASE", request.run_id) is None
    assert store.get_input("ANOTHER_CASE", request.run_id) is None
    assert store.get_lineage("ANOTHER_CASE", request.run_id) == []


@pytest.mark.parametrize(
    "target", ["decision", "aggregation", "risk_rule", "matched_rule", "mapping"]
)
def test_tampered_policy_snapshots_are_rejected_before_any_writes(generated, database_url, target):
    store, request, response, _ = generated
    if target == "decision":
        response.payload.criterion_results[0].tieu_chi_snapshot_json["decision_rule_snapshot_json"][
            "rule_version"
        ] = "FORGED"
    elif target == "aggregation":
        response.payload.requirement_results[0].requirement_snapshot_json["aggregation_policy"][
            "rule_version"
        ] = "FORGED"
    elif target == "risk_rule":
        response.payload.risks[0].rule_snapshot_json["rule_version"] = "FORGED"
    elif target == "matched_rule":
        response.payload.risks[0].rule_snapshot_json["matched_rules"][0]["rule_version"] = "FORGED"
    else:
        response.payload.recommendations[0].template_snapshot_json["mapping_snapshots"][0][
            "lien_ket_id"
        ] = "FOREIGN_MAPPING"
    with pytest.raises(ValueError):
        store.save(request, response)
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM runtime.assessment_runs").fetchone()["n"]
            == 0
        )


def test_retrieval_scores_preserve_dto_decimal_representation(generated, database_url):
    store, request, response, _ = generated
    scores = {
        "bm25_score": 0.30000000000000004,
        "vector_score": 1.2345678901234567,
        "rerank_score": 0.12345678901234567,
    }
    request.payload.retrieval[0].scores = scores
    assert store.save(request, response) == response
    assert store.get_input(request.ca_id, request.run_id) == request
    assert store.save(request, response) == response
    with connect_postgres(database_url) as connection:
        stored = connection.execute(
            "SELECT bm25_score, vector_score, rerank_score "
            "FROM runtime.ket_qua_truy_xuat WHERE truy_xuat_id=%s",
            (request.payload.retrieval[0].truy_xuat_id,),
        ).fetchone()
    assert dict(stored) == {key: Decimal(str(value)) for key, value in scores.items()}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_retrieval_scores_cannot_alias_existing_null_score(generated, value):
    store, request, response, _ = generated
    request.payload.retrieval[0].scores["bm25_score"] = None
    store.save(request, response)
    changed = request.model_copy(deep=True)
    changed.payload.retrieval[0].scores["bm25_score"] = value
    with pytest.raises(ValueError, match="finite"):
        store.save(changed, response)
    assert store.get_input(request.ca_id, request.run_id) == request


@pytest.mark.parametrize("tamper_c09", [False, True])
def test_two_branch_generated_outputs_and_citation_provenance_survive_postgresql(
    generated, database_url, tamper_c09
):
    store, request, compliance_only, knowledge = generated
    # This synthetic upstream finding asserts only missing verification. It does not
    # approve a law/source, add official evidence, or provide reference C10/C11 outputs.
    citation = CitationValidation(
        finding_id="C09_UNVERIFIED_TEST",
        ca_id=request.ca_id,
        vien_dan_id="C03_UNVERIFIED_TEST",
        status="UNKNOWN",
        reason_code="MISSING_OFFICIAL_IDENTITY_AND_DATE",
        ly_do="Need the official document identity, source URL and relevant date",
        domain_status="UNKNOWN",
        finding_verified=False,
        source_snapshot_json={"input_origin": "SYNTHETIC_UNVERIFIED_UPSTREAM_TEST"},
        lan_chay_id=request.run_id,
        knowledge_version=request.legal_knowledge_version,
    )
    request.payload.citations = [citation]
    request.payload.citation_branch_status = "COMPLETED"
    response = evaluate(request, knowledge)
    assert response.payload.criterion_results == compliance_only.payload.criterion_results
    assert response.payload.requirement_results == compliance_only.payload.requirement_results
    assert [row for row in response.payload.risks if row.source.ket_qua_tieu_chi_id] == (
        compliance_only.payload.risks
    )
    assert any(
        item["code"] == "C09_PROVENANCE_UNAVAILABLE" and item["subject_id"] == citation.finding_id
        for item in response.payload.diagnostics
    )
    citation_risks = [row for row in response.payload.risks if row.source.citation_finding_id]
    assert len(citation_risks) == 1, "The real seed UNKNOWN citation rule must produce verification"
    risk = citation_risks[0]
    assert risk.source.citation_finding_id == citation.finding_id
    assert risk.source.ket_qua_tieu_chi_id is None
    assert risk.source.yeu_cau_ca_id is None
    assert risk.risk_type == "VERIFICATION"
    assert risk.severity == "REVIEW_REQUIRED"
    assert risk.rule_snapshot_json["source_finding_snapshot"] == citation.model_dump(mode="json")
    assert "knowledge_snapshot_sha256" not in citation.source_snapshot_json
    mapped_templates = {
        row["khuyen_nghi_id"]
        for row in knowledge.tables["rui_ro_khuyen_nghi"]
        if row["rui_ro_id"] == risk.rui_ro_id
    }
    actions = [
        row
        for row in response.payload.recommendations
        if row.ket_qua_rui_ro_id == risk.ket_qua_rui_ro_id
    ]
    assert mapped_templates
    assert {row.khuyen_nghi_id for row in actions} == mapped_templates
    assert all(
        row.uu_tien == "REVIEW_REQUIRED" and row.review_status == "PENDING" for row in actions
    )
    assert all(citation.ly_do in row.noi_dung for row in actions)

    assert store.save(request, response) == response
    assert store.get(request.ca_id, request.run_id) == response
    assert store.get_input(request.ca_id, request.run_id) == request
    lineage = store.get_lineage(request.ca_id, request.run_id)
    risk_lineage = next(row for row in lineage if row["output_id"] == risk.ket_qua_rui_ro_id)
    assert risk_lineage["payload"] == risk.model_dump(mode="json")
    assert risk_lineage["ca_id"] == request.ca_id
    assert risk_lineage["run_id"] == request.run_id
    for action in actions:
        assert (
            next(row for row in lineage if row["output_id"] == action.khuyen_nghi_ca_id)["payload"][
                "ket_qua_rui_ro_id"
            ]
            == risk.ket_qua_rui_ro_id
        )
    with connect_postgres(database_url) as connection:
        source = connection.execute(
            "SELECT ca_id, lan_chay_id, finding_verified, trang_thai, source_snapshot_json "
            "FROM runtime.phat_hien_vien_dan WHERE finding_id=%s",
            (citation.finding_id,),
        ).fetchone()
        normalized = connection.execute(
            "SELECT nguon_tieu_chi_id, nguon_vien_dan_id, severity_snapshot "
            "FROM runtime.ket_qua_rui_ro WHERE ket_qua_id=%s",
            (risk.ket_qua_rui_ro_id,),
        ).fetchone()
        assert dict(source) == {
            "ca_id": request.ca_id,
            "lan_chay_id": request.run_id,
            "finding_verified": False,
            "trang_thai": "UNKNOWN",
            "source_snapshot_json": citation.source_snapshot_json,
        }
        assert dict(normalized) == {
            "nguon_tieu_chi_id": None,
            "nguon_vien_dan_id": citation.finding_id,
            "severity_snapshot": "REVIEW_REQUIRED",
        }
        if tamper_c09:
            connection.execute(
                "UPDATE runtime.phat_hien_vien_dan SET finding_verified=true WHERE finding_id=%s",
                (citation.finding_id,),
            )
    if tamper_c09:
        for read in (store.get, store.get_input, store.get_lineage):
            with pytest.raises(ValueError, match="normalized phat_hien_vien_dan"):
                read(request.ca_id, request.run_id)
        with pytest.raises(ValueError, match="normalized phat_hien_vien_dan"):
            store.save(request, response)


@pytest.mark.parametrize(
    "finding,expected_status",
    [("SATISFIED", "COMPLIANT"), ("VIOLATED", "NON_COMPLIANT"), ("MISSING", "NON_COMPLIANT")],
)
def test_known_synthetic_observations_generate_and_persist_real_core_outputs(
    database_url, request_factory, finding, expected_status
):
    # The small seed intentionally leaves criterion.dieu_kien SQL NULL. That is
    # a knowledge gap, not an unconditional policy. Define a local synthetic policy
    # only in this isolated test DB before capturing its immutable snapshot.
    with connect_postgres(database_url) as connection:
        connection.execute(
            "UPDATE knowledge.tieu_chi_danh_gia SET dieu_kien=%s WHERE requirement_version_id=%s",
            (
                Jsonb(
                    {
                        "criterion_target_only": True,
                        "local_applicability_only": True,
                        "scope_missing_policy": "UNKNOWN",
                    }
                ),
                "PV_GYC005",
            ),
        )
    knowledge = Knowledge(database_url)
    request = request_factory(finding=finding)
    request.knowledge_snapshot_sha256 = knowledge.sha256
    # Fixture observations represent an explicitly synthetic trusted adapter boundary.
    # No legal outcome/knowledge review is claimed for real-world source documents.
    if finding == "MISSING":
        request.payload.retrieval.clear()
        for observation in request.payload.observations:
            observation.evidence.clear()
    response = evaluate(request, knowledge)
    assert response.payload.criterion_results
    assert {row.finding for row in response.payload.criterion_results} == {finding}, [
        (row.tieu_chi_id, row.uncertainty_reason) for row in response.payload.criterion_results
    ]
    assert {row.status for row in response.payload.requirement_results} == {expected_status}
    assert all(row.review_status == "PENDING" for row in response.payload.criterion_results)
    assert all(
        row.tieu_chi_snapshot_json["human_verified"] is False
        for row in response.payload.criterion_results
    )
    if finding == "SATISFIED":
        assert response.payload.risks == []
        assert response.payload.recommendations == []
    else:
        assert response.payload.risks and response.payload.recommendations
        assert all(row.source.ket_qua_tieu_chi_id for row in response.payload.risks)
        assert all(row.source.citation_finding_id is None for row in response.payload.risks)
        assert {row.ket_qua_rui_ro_id for row in response.payload.recommendations} <= {
            row.ket_qua_rui_ro_id for row in response.payload.risks
        }
    store = Store(database_url)
    assert store.save(request, response) == response
    assert store.get(request.ca_id, request.run_id) == response
    assert store.get_input(request.ca_id, request.run_id) == request
    assert len(store.get_lineage(request.ca_id, request.run_id)) == sum(
        len(getattr(response.payload, attribute)) for attribute, _ in OUTPUTS.values()
    )
    with connect_postgres(database_url) as connection:
        evidence = connection.execute(
            "SELECT trich_dan, ky_tu_bat_dau, ky_tu_ket_thuc FROM runtime.bang_chung_ket_qua"
        ).fetchall()
        if finding == "MISSING":
            assert evidence == []
        else:
            assert len(evidence) == len(response.payload.criterion_results)
            original = request.payload.chunks[0].noi_dung
            assert all(
                original[row["ky_tu_bat_dau"] : row["ky_tu_ket_thuc"]] == row["trich_dan"]
                for row in evidence
            )
