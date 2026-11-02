"""Exercise the offline CLI with real cores and injected Knowledge/Store boundaries."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest
from legal_checker.modules.assessments import run_group_c as runner
from legal_checker.modules.assessments.audit import digest
from legal_checker.modules.assessments.repository import OUTPUTS
from legal_checker.modules.compliance.input_repository import map_profile
from legal_checker.modules.compliance.run_c07 import read_json
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.pipeline import PipelineRequest
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from legal_checker.workflows.steps_5_7 import evaluate
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_group_c_core import configure_downstream


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def test_help_prints_under_windows_legacy_console_encoding_without_database():
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8=0",
            "-m",
            "legal_checker.modules.assessments.run_group_c",
            "--help",
        ],
        env={**os.environ, "PYTHONIOENCODING": "cp1258"},
        capture_output=True,
        text=True,
        encoding="cp1258",
    )
    assert result.returncode == 0, result.stderr
    assert "--read-run" in result.stdout and "--replay-analyses" in result.stdout


def lineage_for(request, response):
    return [
        {
            "table_name": table,
            "output_id": getattr(row, key),
            "ca_id": request.ca_id,
            "run_id": request.run_id,
            "payload": row.model_dump(mode="json"),
        }
        for table, (attribute, key) in OUTPUTS.items()
        for row in getattr(response.payload, attribute)
    ]


@pytest.fixture
def cli_case(reasoning_case, monkeypatch, tmp_path):
    knowledge, data = reasoning_case
    data["payload"]["observations"][0]["proposed_finding"] = "VIOLATED"
    data["payload"]["observations"][0]["gates"].update(
        coverage_complete=True, absence_verified=True
    )
    configure_downstream(knowledge, "VIOLATED")
    request = PipelineRequest(
        **{key: value for key, value in data.items() if key != "payload"},
        payload=data["payload"],
    )
    input_path = dump(tmp_path / "source.json", request.model_dump(mode="json"))
    events = []
    saved = {}

    class MemoryStore:
        def save(self, actual_request, response):
            events.append(("save", actual_request.ca_id, actual_request.run_id))
            key = (actual_request.ca_id, actual_request.run_id)
            saved[key] = (actual_request.model_copy(deep=True), response.model_copy(deep=True))
            return saved[key][1].model_copy(deep=True)

        def get(self, case_id, run_id):
            events.append(("get", case_id, run_id))
            pair = saved.get((case_id, run_id))
            return (
                type(pair[1]).model_validate(
                    json.loads(json.dumps(pair[1].model_dump(mode="json"), sort_keys=True))
                )
                if pair
                else None
            )

        def get_input(self, case_id, run_id):
            events.append(("get_input", case_id, run_id))
            pair = saved.get((case_id, run_id))
            return (
                type(pair[0]).model_validate(
                    json.loads(json.dumps(pair[0].model_dump(mode="json"), sort_keys=True))
                )
                if pair
                else None
            )

        def get_lineage(self, case_id, run_id):
            events.append(("get_lineage", case_id, run_id))
            pair = saved.get((case_id, run_id))
            return lineage_for(*pair) if pair else []

    store = MemoryStore()

    def new_store(url):
        assert url == "memory://group-c-cli"
        events.append(("new_store",))
        return store

    def read_knowledge(url, snapshot):
        assert url == "memory://group-c-cli"
        assert snapshot == knowledge.sha256
        assert "default_transaction_read_only=on" in os.environ["PGOPTIONS"]
        events.append(("knowledge", snapshot))
        return knowledge

    class ReferenceInputs:
        def __init__(self, url):
            assert url == "memory://group-c-cli"

        def load(self, case_id, reference_run):
            assert "default_transaction_read_only=on" in os.environ["PGOPTIONS"]
            events.append(("reference", case_id, reference_run))
            data = request.model_dump()
            data["payload"].pop("citations")
            data["payload"].pop("citation_branch_status")
            data["payload"].pop("reasoning_provenance")
            data["payload"]["observations"] = []
            data.pop("contract_name")
            return SimpleNamespace(
                request=ReasoningRequest(**data),
                profile=map_profile(None, request.payload.hop_dong_id),
                lineage={"source_run_id": reference_run, "reference_outputs_used": False},
            )

    monkeypatch.setattr(
        runner.Settings, "from_env", lambda: SimpleNamespace(database_url="memory://group-c-cli")
    )
    monkeypatch.setattr(runner, "Knowledge", read_knowledge)
    monkeypatch.setattr(runner, "Store", new_store)
    monkeypatch.setattr(runner, "C07InputRepository", ReferenceInputs)
    from legal_checker.shared.llm import client

    def forbidden_client(*args, **kwargs):
        pytest.fail("Group C CLI must never instantiate a paid model client")

    monkeypatch.setattr(client, "OpenAIResponsesClient", forbidden_client)
    monkeypatch.setenv("OPENAI_API_KEY", "unit-secret-never-used")
    return SimpleNamespace(
        knowledge=knowledge,
        request=request,
        input=input_path,
        store=store,
        events=events,
        saved=saved,
        tmp=tmp_path,
    )


@pytest.mark.parametrize(
    "arguments",
    [
        ["--read-run", "RUN", "--save"],
        ["--read-run", "RUN", "--input", "input.json"],
        ["--read-run", "RUN", "--reference-run", "IGNORED"],
        ["--read-run", "RUN", "--profile", "profile.json"],
        ["--read-run", "RUN", "--registry", "registry.json"],
        ["--read-run", "RUN", "--citations-completed"],
        ["--read-run", "RUN", "--citations", "citations.json"],
        ["--read-run", "RUN", "--verifications", "verification.json"],
        ["--read-run", "RUN", "--reviews", "reviews.json"],
        ["--read-run", "RUN", "--replay-analyses", "analyses.json"],
        ["--replay-analyses", "analyses.json"],
        ["--reviews", "reviews.json"],
        ["--input", "input.json", "--reference-run", "REF"],
        ["--input", "input.json", "--profile", "profile.json"],
        ["--input", "input.json", "--verifications", "verification.json"],
        ["--case", "   "],
        ["--read-run", ""],
        ["--reference-run", ""],
        ["--live"],
    ],
)
def test_invalid_flags_are_rejected_before_settings_database_or_provider(monkeypatch, arguments):
    def forbidden():
        pytest.fail("Invalid CLI flags must be rejected before configuration or I/O")

    monkeypatch.setattr(runner.Settings, "from_env", forbidden)
    with pytest.raises(SystemExit) as error:
        runner.main(arguments)
    assert error.value.code == 2


def test_reference_mode_runs_real_cores_without_promoting_reference_answers(cli_case, capsys):
    output = cli_case.tmp / "offline"
    prior_pgoptions = os.environ.get("PGOPTIONS")
    assert runner.main(["--case", "CASE_1", "--output-dir", str(output)]) == 0
    metadata = read_json(output / "metadata.json")
    assert metadata["mode"] == "OFFLINE_REFERENCE_UPSTREAM"
    assert metadata["paid_api_attempts"] == 0
    assert metadata["db_results_saved"] is False
    assert metadata["recomputed"] is True
    assert metadata["counts"] == {
        "c05": 1,
        "c06": 1,
        "c07": 1,
        "c08": 1,
        "c09": 0,
        "c10": 0,
        "c11": 0,
    }
    assert metadata["findings"] == {"UNKNOWN": 1}
    assert metadata["requirement_statuses"] == {"INSUFFICIENT": 1}
    assert metadata["analysis_origins"] == {"NO_CALL": 1}
    assert metadata["citation_branch_status"] == "NOT_RUN"
    assert metadata["source_lineage"]["reference_outputs_used"] is False
    assert read_json(output / "c07.json")[0]["uncertainty_reason"]
    assert read_json(output / "reviews.json") == []
    assert read_json(output / "registry.json") == []
    assert read_json(output / "citations.json") == []
    assert not (output / "lineage.json").exists()
    assert ("reference", "CASE_1", "CASE_1_PDF360_LS2_REFERENCE") in cli_case.events
    assert not any(event[0] in {"new_store", "save"} for event in cli_case.events)
    assert os.environ.get("PGOPTIONS") == prior_pgoptions
    assert "unit-secret" not in capsys.readouterr().out


def test_input_mode_exports_real_findings_exact_hashes_and_counts(cli_case):
    output = cli_case.tmp / "input-output"
    assert runner.main(["--input", str(cli_case.input), "--output-dir", str(output)]) == 0
    actual_input = PipelineRequest.model_validate(read_json(output / "input.json"))
    actual_output = runner.PipelineResponse.model_validate(read_json(output / "output.json"))
    metadata = read_json(output / "metadata.json")
    assert actual_input == cli_case.request
    assert actual_output.payload.criterion_results[0].finding == "VIOLATED"
    assert actual_output.payload.requirement_results[0].status == "NON_COMPLIANT"
    assert metadata["counts"]["c10"] == metadata["counts"]["c11"] == 1
    assert metadata["input_sha256"] == digest(actual_input)
    assert metadata["output_sha256"] == digest(actual_output)
    assert metadata["mode"] == "OFFLINE_INPUT"
    assert metadata["analysis_origins"] == {}
    assert metadata["produced_at_utc"] == actual_output.produced_at.isoformat()
    assert read_json(output / "c10.json")[0]["source"]["ket_qua_tieu_chi_id"] == (
        actual_output.payload.criterion_results[0].ket_qua_id
    )
    assert read_json(output / "c11.json")[0]["ket_qua_rui_ro_id"] == (
        actual_output.payload.risks[0].ket_qua_rui_ro_id
    )
    assert not any(event[0] in {"new_store", "save"} for event in cli_case.events)


def test_citation_sidecar_keeps_unknown_provenance_and_branch_status(cli_case):
    request = cli_case.request
    citations = [
        {
            "finding_id": "UNKNOWN_C09",
            "ca_id": request.ca_id,
            "vien_dan_id": "C03_SYNTHETIC",
            "status": "UNKNOWN",
            "reason_code": "MISSING_SOURCE",
            "ly_do": "Need official source identity",
            "domain_status": "UNKNOWN",
            "finding_verified": False,
            "source_snapshot_json": {},
            "lan_chay_id": request.run_id,
            "knowledge_version": request.legal_knowledge_version,
        }
    ]
    path = dump(cli_case.tmp / "citations-source.json", citations)
    output = cli_case.tmp / "with-citations"
    assert (
        runner.main(
            ["--input", str(cli_case.input), "--citations", str(path), "--output-dir", str(output)]
        )
        == 0
    )
    metadata = read_json(output / "metadata.json")
    assert metadata["counts"]["c09"] == 1
    assert metadata["citation_branch_status"] == "COMPLETED"
    assert read_json(output / "citations.json") == [
        CitationValidation.model_validate(item).model_dump(mode="json") for item in citations
    ]
    assert read_json(output / "citations.json")[0]["source_snapshot_json"] == {}
    assert any(
        row["code"] == "C09_PROVENANCE_UNAVAILABLE"
        for row in read_json(output / "diagnostics.json")
    )


def test_explicit_completed_empty_citation_is_retained(cli_case):
    output = cli_case.tmp / "completed-empty"
    assert (
        runner.main(
            ["--input", str(cli_case.input), "--citations-completed", "--output-dir", str(output)]
        )
        == 0
    )
    assert read_json(output / "metadata.json")["citation_branch_status"] == "COMPLETED"
    assert read_json(output / "input.json")["payload"]["citation_branch_status"] == "COMPLETED"


def test_save_and_read_export_exact_case_run_without_engine_or_knowledge(cli_case, monkeypatch):
    saved_output = cli_case.tmp / "saved"
    assert (
        runner.main(["--input", str(cli_case.input), "--save", "--output-dir", str(saved_output)])
        == 0
    )
    request, response = cli_case.saved[(cli_case.request.ca_id, cli_case.request.run_id)]
    expected_lineage = lineage_for(request, response)
    assert read_json(saved_output / "lineage.json") == expected_lineage
    cli_case.events.clear()

    def forbidden(*args, **kwargs):
        pytest.fail("read-run must only read saved DTOs and membership, never run engines")

    for name in (
        "run_pipeline",
        "run_assessment",
        "Knowledge",
        "C07InputRepository",
        "LLMObservationProvider",
    ):
        monkeypatch.setattr(runner, name, forbidden)
    output = cli_case.tmp / "read"
    assert (
        runner.main(
            ["--read-run", request.run_id, "--case", request.ca_id, "--output-dir", str(output)]
        )
        == 0
    )
    assert read_json(output / "input.json") == read_json(saved_output / "input.json")
    assert read_json(output / "output.json") == read_json(saved_output / "output.json")
    for name in ("input.json", "output.json", "c07.json", "c08.json", "c10.json", "c11.json"):
        assert (output / name).read_bytes() == (saved_output / name).read_bytes()
    assert read_json(output / "lineage.json") == expected_lineage
    saved_meta = read_json(saved_output / "metadata.json")
    read_meta = read_json(output / "metadata.json")
    assert read_meta["input_sha256"] == saved_meta["input_sha256"]
    assert read_meta["output_sha256"] == saved_meta["output_sha256"]
    assert read_meta["counts"] == saved_meta["counts"]
    assert read_meta["mode"] == "READ_SAVED"
    assert read_meta["db_results_saved"] is True
    assert read_meta["recomputed"] is False
    assert not any(event[0] in {"save", "reference", "knowledge"} for event in cli_case.events)
    assert cli_case.events == [
        ("new_store",),
        ("get", request.ca_id, request.run_id),
        ("get_input", request.ca_id, request.run_id),
        ("get_lineage", request.ca_id, request.run_id),
    ]


@pytest.mark.parametrize("case_id,run_id", [("CASE_1", "MISSING"), ("OTHER_CASE", "RUN_1")])
def test_read_absent_run_does_not_fall_back_to_latest(cli_case, case_id, run_id):
    cli_case.store.save(cli_case.request, evaluate(cli_case.request, cli_case.knowledge))
    output = cli_case.tmp / "absent"
    assert runner.main(["--case", case_id, "--read-run", run_id, "--output-dir", str(output)]) == 1
    assert not output.exists()


def test_case_argument_cannot_silently_override_input_case(cli_case):
    output = cli_case.tmp / "wrong-case"
    assert (
        runner.main(
            ["--input", str(cli_case.input), "--case", "OTHER_CASE", "--output-dir", str(output)]
        )
        == 1
    )
    assert not output.exists()
    assert cli_case.events == []


def test_old_output_directory_is_untouched_before_any_evaluation(cli_case):
    output = cli_case.tmp / "existing"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("prior evidence", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        runner.main(["--input", str(cli_case.input), "--output-dir", str(output)])
    assert error.value.code == 2
    assert sentinel.read_text(encoding="utf-8") == "prior evidence"
    assert list(output.iterdir()) == [sentinel]
    assert cli_case.events == []


def test_export_failure_leaves_no_partial_artifacts_or_source_disclosure(
    cli_case, monkeypatch, capsys
):
    original = runner.write_json

    def fail_after_input(path, value):
        if path.name == "output.json":
            raise OSError("unit-secret-sensitive-source")
        return original(path, value)

    monkeypatch.setattr(runner, "write_json", fail_after_input)
    output = cli_case.tmp / "failed"
    assert runner.main(["--input", str(cli_case.input), "--output-dir", str(output)]) == 1
    assert not output.exists()
    assert not list(cli_case.tmp.glob(".failed.*"))
    captured = capsys.readouterr()
    assert "unit-secret" not in captured.out + captured.err
    assert "OSError" in captured.err


def test_export_does_not_overwrite_directory_created_during_staging(cli_case, monkeypatch):
    original = runner.write_json
    output = cli_case.tmp / "raced"

    def create_other_output(path, value):
        original(path, value)
        if path.name == "metadata.json":
            output.mkdir()
            (output / "keep.txt").write_text("other export", encoding="utf-8")

    monkeypatch.setattr(runner, "write_json", create_other_output)
    assert runner.main(["--input", str(cli_case.input), "--output-dir", str(output)]) == 1
    assert (output / "keep.txt").read_text(encoding="utf-8") == "other export"
    assert not (output / "metadata.json").exists()
    assert not list(cli_case.tmp.glob(".raced.*"))


@pytest.mark.parametrize("corruption", ["missing", "foreign-run", "payload", "duplicate"])
def test_export_rejects_inconsistent_saved_lineage_before_files(cli_case, corruption):
    request = cli_case.request
    response = evaluate(request, cli_case.knowledge)
    lineage = lineage_for(request, response)
    if corruption == "missing":
        lineage.pop()
    elif corruption == "foreign-run":
        lineage[0]["run_id"] = "OTHER_RUN"
    elif corruption == "payload":
        lineage[0]["payload"] = {}
    else:
        lineage.append(deepcopy(lineage[0]))
    output = cli_case.tmp / "invalid-lineage"
    with pytest.raises(ValueError, match="lineage"):
        runner.export_run(
            output,
            request,
            response,
            {"mode": "READ_SAVED", "db_results_saved": True},
            lineage=lineage,
        )
    assert not output.exists()


def test_export_rejects_response_from_another_context(cli_case):
    response = evaluate(cli_case.request, cli_case.knowledge)
    response.run_id = "OTHER_RUN"
    output = cli_case.tmp / "foreign-output"
    with pytest.raises(ValueError, match="context"):
        runner.export_run(
            output, cli_case.request, response, {"mode": "READ_SAVED", "db_results_saved": False}
        )
    assert not output.exists()


def test_exported_offline_analysis_can_replay_with_exact_profile_and_no_model(cli_case):
    initial = cli_case.tmp / "initial-analysis"
    assert runner.main(["--case", "CASE_1", "--output-dir", str(initial)]) == 0
    replayed = cli_case.tmp / "replayed-analysis"
    assert (
        runner.main(
            [
                "--input",
                str(initial / "input.json"),
                "--replay-analyses",
                str(initial / "analyses.json"),
                "--profile",
                str(initial / "profile.json"),
                "--verifications",
                str(initial / "verifications.json"),
                "--output-dir",
                str(replayed),
            ]
        )
        == 0
    )
    metadata = read_json(replayed / "metadata.json")
    assert metadata["mode"] == "REPLAY"
    assert metadata["analysis_origins"] == {"REPLAY": 1}
    assert metadata["paid_api_attempts"] == 0
    assert read_json(replayed / "c07.json") == read_json(initial / "c07.json")
    assert read_json(replayed / "c08.json") == read_json(initial / "c08.json")
    assert read_json(replayed / "c10.json") == read_json(initial / "c10.json")
    assert read_json(replayed / "c11.json") == read_json(initial / "c11.json")
    assert read_json(replayed / "reviews.json") == []


@pytest.mark.parametrize("corruption", ["missing-profile", "foreign-digest", "foreign-run"])
def test_replay_rejects_changed_original_bindings_without_artifacts(cli_case, corruption):
    initial = cli_case.tmp / "bound-analysis"
    assert runner.main(["--case", "CASE_1", "--output-dir", str(initial)]) == 0
    input_path = initial / "input.json"
    analysis_path = initial / "analyses.json"
    if corruption == "foreign-digest":
        analyses = read_json(analysis_path)
        analyses[0]["input_sha256"] = "f" * 64
        analysis_path = dump(cli_case.tmp / "wrong-digest.json", analyses)
    elif corruption == "foreign-run":
        source = read_json(input_path)
        source["run_id"] = "OTHER_RUN"
        source["payload"]["retrieval"][0]["lan_chay_id"] = "OTHER_RUN"
        input_path = dump(cli_case.tmp / "wrong-run.json", source)
    output = cli_case.tmp / "replay-rejected"
    arguments = [
        "--input",
        str(input_path),
        "--replay-analyses",
        str(analysis_path),
        "--output-dir",
        str(output),
    ]
    if corruption != "missing-profile":
        arguments.extend(["--profile", str(initial / "profile.json")])
    assert runner.main(arguments) == 1
    assert not output.exists()
