import json
import shutil
import subprocess
import sys
from copy import copy

import pytest
from devtools.fixture_builder import build_scenario
from devtools.parallel import FIXTURE_ROOT, SCENARIOS, FixturePack, json_text
from legal_checker.core.config import PROJECT_ROOT


def test_fixture_regeneration_is_reproducible(parallel_packs, knowledge):
    for scenario in SCENARIOS:
        handoffs, source = build_scenario(scenario, knowledge)
        pack = parallel_packs[scenario]
        assert handoffs == pack.handoffs
        assert source == pack.read_source(pack.handoffs.document_input.case.source)


def test_loader_rejects_modified_fixture_files(tmp_path, knowledge):
    directory = tmp_path / "case"
    shutil.copytree(FIXTURE_ROOT / "satisfied", directory)
    (directory / "retrieval_output.json").write_text("[]\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        FixturePack.load(directory, knowledge)


def test_loader_rejects_a_different_knowledge_release(knowledge):
    other = copy(knowledge)
    other.sha256 = "0" * 64
    with pytest.raises(ValueError, match="knowledge checksum"):
        FixturePack.load(FIXTURE_ROOT / "satisfied", other)


def test_cli_checks_an_owners_output_and_exits_nonzero_for_a_bad_handoff(
    tmp_path, parallel_packs, knowledge
):
    pack = parallel_packs["satisfied"]
    output = pack.reference_output(3, knowledge)
    file = tmp_path / "retrieval.json"
    file.write_text(json_text(output))
    command = [
        sys.executable,
        "-m",
        "scripts.parallel_dev",
        "--person",
        "3",
        "--verify-output",
        str(file),
    ]
    passed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert passed.returncode == 0, passed.stderr
    assert json.loads(passed.stdout)["results"][0]["mode"] == "validate_external_output"
    raw = json.loads(file.read_text())
    raw[0]["doan_id"] = "FOREIGN_CHUNK"
    file.write_text(json.dumps(raw))
    failed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert failed.returncode == 1
    assert "foreign" in failed.stderr
