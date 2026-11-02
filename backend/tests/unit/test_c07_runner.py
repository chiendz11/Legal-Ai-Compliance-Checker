"""Offline composition and input loading: no database, API or generated approvals."""

import json
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest
from legal_checker.modules.compliance import input_repository
from legal_checker.modules.compliance import run_c07 as runner
from legal_checker.modules.compliance.input_repository import (
    C07InputRepository,
    fork_reference_request,
    map_profile,
    readonly_database,
)
from legal_checker.modules.compliance.llm_contracts import CriterionAnalysis, ObservationBatch
from legal_checker.modules.compliance.run_c07 import (
    JsonlAuditSink,
    build_parser,
    read_json,
    read_models,
    run_assessment,
    save_run,
)
from legal_checker.shared.contracts.reasoning import Observation, ReasoningRequest
from test_criterion_reasoner import reasoning_case as reasoning_case


def fake_batch(request):
    observations = [item.model_copy(deep=True) for item in request.payload.observations]
    return ObservationBatch(
        observations=observations,
        analyses=[
            CriterionAnalysis(
                tieu_chi_id=item.tieu_chi_id,
                input_sha256="a" * 64,
                origin="NO_CALL",
                model_version="SYNTHETIC_BACKEND_FIXTURE",
                prompt_version="NOT_USED",
                observation_proposal=item,
                observation=item,
            )
            for item in observations
        ],
    )


def test_run_assessment_uses_provider_then_pure_reasoner_without_mutating_input(reasoning_case):
    knowledge, data = reasoning_case
    request = ReasoningRequest.model_validate(data)
    before = request.model_dump()
    calls = []

    def analyze(actual, actual_knowledge, **kwargs):
        calls.append((actual, actual_knowledge, kwargs))
        return fake_batch(actual)

    run = run_assessment(request, knowledge, provider=SimpleNamespace(analyze=analyze))

    assert len(calls) == 1
    assert run.results[0].finding == "SATISFIED"
    assert run.request.payload.observations == run.batch.observations
    assert request.model_dump() == before
    assert run.request is not request


def test_incomplete_provider_output_cannot_hide_a_criterion(reasoning_case):
    knowledge, data = reasoning_case
    request = ReasoningRequest.model_validate(data)
    provider = SimpleNamespace(
        analyze=lambda *a, **kw: ObservationBatch(observations=[], analyses=[])
    )
    with pytest.raises(ValueError, match="checklist"):
        run_assessment(request, knowledge, provider=provider)


def test_provider_cannot_modify_its_input(reasoning_case):
    knowledge, data = reasoning_case
    request = ReasoningRequest.model_validate(data)

    def analyze(actual, *args, **kwargs):
        actual.payload.requirements[0].scope_status = "UNKNOWN"
        return fake_batch(actual)

    with pytest.raises(ValueError, match="changed input"):
        run_assessment(request, knowledge, provider=SimpleNamespace(analyze=analyze))
    assert request.payload.requirements[0].scope_status == "MATCH"


def test_fork_clones_selected_retrieval_and_preserves_reference_lineage(reasoning_case):
    _, data = reasoning_case
    reference = ReasoningRequest.model_validate(data)
    before = reference.model_dump()

    dev, lineage = fork_reference_request(reference)

    assert reference.model_dump() == before
    assert dev.run_id != reference.run_id
    assert dev.trace_id != reference.trace_id
    assert dev.payload.observations == []
    assert len(dev.payload.retrieval) == len(reference.payload.retrieval)
    dev_c06 = dev.payload.retrieval[0]
    ref_c06 = reference.payload.retrieval[0]
    assert dev_c06.truy_xuat_id != ref_c06.truy_xuat_id
    assert dev_c06.lan_chay_id == dev.run_id
    assert dev_c06.doan_id == ref_c06.doan_id
    assert dev_c06.duoc_chon is True
    assert lineage["source_run_id"] == reference.run_id
    assert lineage["retrieval"][0]["source_truy_xuat_id"] == ref_c06.truy_xuat_id
    assert lineage["retrieval"][0]["dev_truy_xuat_id"] == dev_c06.truy_xuat_id


def test_readonly_scope_restores_environment_even_on_error(monkeypatch):
    monkeypatch.setenv("PGOPTIONS", "-c timezone=UTC")
    with pytest.raises(RuntimeError), readonly_database():
        assert input_repository.os.environ["PGOPTIONS"].endswith("default_transaction_read_only=on")
        raise RuntimeError("fixture")
    assert input_repository.os.environ["PGOPTIONS"] == "-c timezone=UTC"
    monkeypatch.delenv("PGOPTIONS")
    with readonly_database():
        assert "read_only=on" in input_repository.os.environ["PGOPTIONS"]
    assert "PGOPTIONS" not in input_repository.os.environ


def test_c02_nullable_storage_does_not_gain_verification():
    profile = map_profile(
        {
            "hop_dong_id": "CONTRACT",
            "la_hop_dong_theo_mau": "UNKNOWN",
            "ben_ban_co_von_nuoc_ngoai": "false",
            "ben_ban_la_chu_dau_tu": True,
        },
        "CONTRACT",
    )
    assert profile.profile.la_hop_dong_theo_mau is None
    assert profile.profile.ben_ban_co_von_nuoc_ngoai is False
    assert profile.profile.ben_ban_la_chu_dau_tu is True
    assert profile.facts == profile.evidence == []
    assert map_profile(None, "CONTRACT").profile.ngay_giao_ket is None
    with pytest.raises(ValueError, match="another contract"):
        map_profile({"hop_dong_id": "OTHER"}, "CONTRACT")


def test_input_repository_loads_all_c05_but_only_selected_final_c06(reasoning_case, monkeypatch):
    knowledge, data = reasoning_case
    request = ReasoningRequest.model_validate(data)
    requirement = request.payload.requirements[0].model_dump()
    requirement["ly_do"] = json.dumps(requirement.pop("reason"))
    retrieval = request.payload.retrieval[0].model_dump(exclude={"scores"})
    retrieval.update(bm25_score=None, vector_score=None, rerank_score=None)
    rows = [
        retrieval,
        {**retrieval, "truy_xuat_id": "NOT_SELECTED", "duoc_chon": False},
        {**retrieval, "truy_xuat_id": "CANDIDATE", "giai_doan": "CANDIDATE"},
    ]
    source = {
        "case": {
            key: getattr(request, key)
            for key in (
                "ca_id",
                "phien_ban_id",
                "rule_version",
                "legal_knowledge_version",
            )
        }
        | {"hop_dong_id": request.payload.hop_dong_id},
        "requirements": [requirement],
        "chunks": [item.model_dump() for item in request.payload.chunks],
    }
    source_before = deepcopy(source)

    class Repository:
        def __init__(self, url):
            assert url == "memory://not-a-real-connection"

        def load_input_rows(self, case_id):
            assert "read_only=on" in input_repository.os.environ["PGOPTIONS"]
            assert case_id == request.ca_id
            return source

        def load_seeded_evidence(self, case_id, reference_run):
            assert reference_run == request.run_id
            return rows

    class Connection:
        def execute(self, query, params=None):
            if query.startswith("SHOW"):
                return SimpleNamespace(fetchone=lambda: {"transaction_read_only": "on"})
            if "qa.case_manifest" in query:
                return SimpleNamespace(
                    fetchone=lambda: {"knowledge_snapshot_sha256": knowledge.sha256}
                )
            assert "runtime.ho_so_hop_dong" in query
            return SimpleNamespace(fetchone=lambda: {"hop_dong_id": request.payload.hop_dong_id})

    @contextmanager
    def connect(url):
        assert "read_only=on" in input_repository.os.environ["PGOPTIONS"]
        yield Connection()

    monkeypatch.setattr(input_repository, "RetrievalDatasetRepository", Repository)
    monkeypatch.setattr(input_repository, "connect_postgres", connect)

    loaded = C07InputRepository("memory://not-a-real-connection").load(
        request.ca_id, request.run_id
    )

    assert loaded.read_only is True
    assert len(loaded.request.payload.requirements) == 1
    assert len(loaded.request.payload.retrieval) == 1
    assert loaded.request.payload.retrieval[0].giai_doan == "FINAL"
    assert loaded.lineage["raw_c06_count"] == 3
    assert source == source_before


def test_saved_package_separates_inputs_proposals_and_c07(reasoning_case, tmp_path):
    knowledge, data = reasoning_case
    request = ReasoningRequest.model_validate(data)
    run = run_assessment(
        request,
        knowledge,
        provider=SimpleNamespace(analyze=lambda actual, *a, **kw: fake_batch(actual)),
    )

    save_run(tmp_path, run, source_input=data, metadata={"mode": "OFFLINE_SYNTHETIC_TEST"})

    metadata = read_json(tmp_path / "metadata.json")
    assert metadata["observations"] == 1
    assert metadata["findings"] == {"SATISFIED": 1}
    assert metadata["db_results_saved"] is False
    assert (
        read_json(tmp_path / "input.json")["payload"]["observations"][0]["tieu_chi_id"]
        == "CRITERION_1"
    )
    bindings = read_json(tmp_path / "review_bindings.json")
    assert bindings[0]["proposal_sha256"]
    assert "gates" not in bindings[0] and "predicate_verified" not in bindings[0]
    assert read_json(tmp_path / "verifications.json") == []
    assert read_json(tmp_path / "profile.json") is None
    assert metadata["verification_records"] == 0
    assert "OFFLINE_SYNTHETIC_TEST" in (tmp_path / "report.md").read_text(encoding="utf-8")
    assert data["run_id"] == "RUN_1"


@pytest.mark.parametrize("text", ["{}", '{"a":1,"a":2}', '{"a":NaN}'])
def test_sidecar_rejects_wrong_shape_or_ambiguous_json(tmp_path, text):
    path = tmp_path / "sidecar.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        if text == "{}":
            read_models(path, Observation)
        else:
            read_json(path)


def test_cli_is_offline_until_explicitly_requested():
    parser = build_parser()
    assert parser.parse_args([]).live is False
    assert parser.parse_args([]).max_calls == 1
    assert parser.parse_args(["--live", "--criterion", "CRITERION_1"]).live is True


def test_jsonl_audit_sink_starts_empty_without_fake_calls(tmp_path):
    path = tmp_path / "audit.jsonl"
    sink = JsonlAuditSink(path)
    assert sink.count == 0 and path.read_text(encoding="utf-8") == ""
    with pytest.raises(FileExistsError):
        JsonlAuditSink(path)


def test_cli_offline_does_not_call_api_even_when_key_is_present(
    reasoning_case, monkeypatch, tmp_path, capsys
):
    knowledge, data = reasoning_case
    input_path = tmp_path / "source.json"
    input_path.write_text(json.dumps(data), encoding="utf-8")
    output = tmp_path / "result"
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-secret-must-not-be-used")
    monkeypatch.setattr(
        runner.Settings, "from_env", lambda: SimpleNamespace(database_url="memory://db")
    )

    def load_knowledge(database_url, *, snapshot_sha256):
        assert database_url == "memory://db"
        assert snapshot_sha256 == knowledge.sha256
        return knowledge

    monkeypatch.setattr(runner, "Knowledge", load_knowledge)
    from legal_checker.shared.llm import client

    def forbidden(*args, **kwargs):
        pytest.fail("Offline CLI must not create an API client")

    monkeypatch.setattr(client, "OpenAIResponsesClient", forbidden)

    code = runner.main(["--input", str(input_path), "--output-dir", str(output)])

    assert code == 0
    metadata = read_json(output / "metadata.json")
    assert metadata["mode"] == "OFFLINE"
    assert metadata["audit_attempts"] == 0
    assert metadata["observations"] == 1
    assert metadata["findings"] == {"UNKNOWN": 1}
    assert (output / "llm_audit.jsonl").read_text(encoding="utf-8") == ""
    assert "unit-test-secret" not in capsys.readouterr().out


def test_cli_live_configuration_error_is_actionable_without_network(
    reasoning_case, monkeypatch, tmp_path, capsys
):
    knowledge, data = reasoning_case
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(
        runner.Settings, "from_env", lambda: SimpleNamespace(database_url="memory://db")
    )
    monkeypatch.setattr(runner, "Knowledge", lambda *args, **kwargs: knowledge)
    from legal_checker.shared.llm.config import LlmConfigurationError, OpenAISettings

    def missing_model():
        raise LlmConfigurationError("OPENAI_MODEL is required")

    monkeypatch.setattr(OpenAISettings, "from_env", missing_model)

    assert (
        runner.main(["--input", str(path), "--live", "--output-dir", str(tmp_path / "live")]) == 1
    )
    assert "OPENAI_MODEL" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [
        ["--live", "--replay-analyses", "prior.json", "--input", "input.json"],
        ["--replay-analyses", "prior.json"],
        ["--max-calls", "-1"],
    ],
)
def test_invalid_cli_combinations_are_rejected_before_any_call(args):
    with pytest.raises(SystemExit) as error:
        runner.main(args)
    assert error.value.code == 2


def test_cli_loads_preanalysis_verification_without_approving_a_proposal(
    reasoning_case, monkeypatch, tmp_path
):
    knowledge, data = reasoning_case
    path = tmp_path / "source.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    verification = {key: value for key, value in data.items() if key != "payload"}
    verification.update(
        hop_dong_id=data["payload"]["hop_dong_id"],
        yeu_cau_ca_id="CASE_REQUIREMENT_1",
        tieu_chi_id="CRITERION_1",
        verification_reference="memory://independent-verification",
        gates={"source_verified": True, "scope_confirmed": True, "version_resolved": True},
        local_applicability="MATCH",
        facts={"condition_triggered": True},
        facts_verified=True,
    )
    verification_path = tmp_path / "verification.json"
    verification_path.write_text(json.dumps([verification]), encoding="utf-8")
    profile = map_profile(
        {"hop_dong_id": data["payload"]["hop_dong_id"]}, data["payload"]["hop_dong_id"]
    )
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(
        runner.Settings, "from_env", lambda: SimpleNamespace(database_url="memory://db")
    )
    monkeypatch.setattr(runner, "Knowledge", lambda *a, **kw: knowledge)
    output = tmp_path / "with-verification"

    assert (
        runner.main(
            [
                "--input",
                str(path),
                "--verifications",
                str(verification_path),
                "--profile",
                str(profile_path),
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )

    saved = read_json(output / "verifications.json")
    assert saved[0]["facts"] == {"condition_triggered": True}
    assert saved[0]["verification_reference"] == "memory://independent-verification"
    assert "predicate_verified" not in saved[0] and "proposal_sha256" not in saved[0]
    metadata = read_json(output / "metadata.json")
    assert metadata["verification_records"] == 1
    assert metadata["profile_context_present"] is True
    assert read_json(output / "profile.json")["hop_dong_id"] == data["payload"]["hop_dong_id"]
    assert metadata["audit_attempts"] == 0
    assert read_json(output / "c07.json")[0]["finding"] == "UNKNOWN"

    replay_output = tmp_path / "replay-with-same-context"
    replay_arguments = [
        "--input",
        str(output / "input.json"),
        "--profile",
        str(output / "profile.json"),
        "--verifications",
        str(output / "verifications.json"),
        "--replay-analyses",
        str(output / "analyses.json"),
    ]
    assert runner.main([*replay_arguments, "--output-dir", str(replay_output)]) == 0
    replay_metadata = read_json(replay_output / "metadata.json")
    assert replay_metadata["analysis_origins"] == {"REPLAY": 1}
    assert replay_metadata["audit_attempts"] == 0
    assert read_json(replay_output / "c07.json") == read_json(output / "c07.json")

    without_profile = list(replay_arguments)
    profile_flag = without_profile.index("--profile")
    del without_profile[profile_flag : profile_flag + 2]
    assert runner.main([*without_profile, "--output-dir", str(tmp_path / "missing-profile")]) == 1
