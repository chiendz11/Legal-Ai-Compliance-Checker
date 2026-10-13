from copy import deepcopy

import pytest
from devtools.database_schema import TABLES
from devtools.database_seed import SeedError, WorkbookSeed, read_workbook
from devtools.qa_schema import QA_TABLES
from devtools.qa_validation import join_artifacts, validate_qa
from devtools.workbook_optimization import artifact, split_cases, subset_release, write_release


def sample():
    seed = WorkbookSeed("a" * 64, {t.name: [] for t in TABLES}, {t.name: [] for t in QA_TABLES})

    def add(name, **values):
        table = next(t for t in TABLES if t.name == name)
        row = dict.fromkeys(k for k, _ in table.columns)
        row.update(values)
        seed.tables[name].append(row)

    add("hop_dong", hop_dong_id="DOC", ho_mau_id="FAMILY")
    add("ca_danh_gia", ca_id="CASE", hop_dong_id="DOC")
    seed.qa_tables["case_manifest"].append(
        {
            "case_id": "CASE",
            "hop_dong_id": "DOC",
            "group_id": "FAMILY",
            "split": "TEST",
            "case_kind": "CORPUS",
            "label_quality": "SILVER_GUARD_REFERENCE",
            "dataset_version": "test",
            "label_version": "test",
            "knowledge_snapshot_sha256": "a" * 64,
            "module_scope": "C01",
            "limitations_json": {"legal_gold": False},
        }
    )
    artifact(seed.qa_tables, "CASE", "INPUT", "DocumentInput", "CASE", {"source": "real input"})
    artifact(
        seed.qa_tables, "CASE", "EXPECTED", "C07", "CASE", {"secret_expected_label": "UNKNOWN"}
    )
    artifact(seed.qa_tables, "CASE", "PROPOSAL", "Legacy", "CASE", {"old_label": "SATISFIED"})
    return seed


def test_multipart_artifact_roundtrip_and_tamper_detection():
    qa = {"artifacts": []}
    value = {"text": "Nguồn pháp lý " * 10000}
    artifact(qa, "CASE", "EXPECTED", "C13", "REPORT", value)
    assert len(qa["artifacts"]) > 1
    assert next(iter(join_artifacts(qa["artifacts"]).values())) == value
    broken = deepcopy(qa["artifacts"])
    broken[-1]["content"] += "x"
    with pytest.raises(SeedError, match="checksum"):
        join_artifacts(broken)
    with pytest.raises(SeedError, match="Incomplete"):
        join_artifacts(qa["artifacts"][:-1])


def test_blind_input_pack_has_no_targets_or_proposals():
    seed = sample()
    seed.qa_tables["case_manifest"][0]["limitations_json"]["scenario"] = "SECRET_VIOLATION"
    seed.qa_tables["controlled_assertions"].append(
        {
            "case_id": "CASE",
            "expected_assertions_json": {"finding": "VIOLATED"},
            "rationale": "Secret expected label",
            "legal_review_id": None,
        }
    )
    blind = subset_release(seed, {"TEST"}, hide_expected=True)
    assert [r["role"] for r in blind.qa_tables["artifacts"]] == ["INPUT"]
    assert [r["contract_name"] for r in blind.qa_tables["artifacts"]] == ["DocumentInput"]
    assert blind.qa_tables["change_log"] == []
    assert blind.qa_tables["controlled_assertions"] == []
    assert "scenario" not in blind.qa_tables["case_manifest"][0]["limitations_json"]
    assert blind.tables["ca_danh_gia"][0]["profile_snapshot_json"] == {
        "evaluation_mode": "RAW_INPUT_ONLY"
    }
    assert all(
        not blind.tables[t.name]
        for t in TABLES
        if t.schema == "runtime" and t.name not in ("hop_dong", "tep_nguon", "ca_danh_gia")
    )
    assert len(seed.qa_tables["artifacts"]) == 3


def test_write_only_workbook_trailing_nulls_and_qa_roundtrip(tmp_path):
    seed = sample()
    path = tmp_path / "sample.xlsx"
    write_release(seed, path, "MASTER")
    actual = read_workbook(path)
    assert actual.counts == seed.counts
    assert actual.qa_counts == seed.qa_counts
    assert actual.tables["ca_danh_gia"][0]["created_by"] is None
    assert actual.qa_tables["case_manifest"][0]["limitations_json"] == {"legal_gold": False}


def test_document_family_cannot_cross_splits():
    seed = sample()
    seed.tables["ca_danh_gia"].append({**seed.tables["ca_danh_gia"][0], "ca_id": "CASE2"})
    seed.qa_tables["case_manifest"].append(
        {**seed.qa_tables["case_manifest"][0], "case_id": "CASE2", "split": "DEV"}
    )
    with pytest.raises(SeedError, match="family crosses"):
        validate_qa(seed)


@pytest.mark.parametrize(
    "field,value", [("case_kind", "WRONG"), ("label_quality", "UNSUPPORTED_NEW_LABEL")]
)
def test_manifest_enums_match_sql_before_export(field, value):
    seed = sample()
    seed.qa_tables["case_manifest"][0][field] = value
    with pytest.raises(SeedError, match=field):
        validate_qa(seed)


def test_split_is_deterministic_and_family_indivisible():
    cases = [{"ca_id": str(i), "hop_dong_id": str(i)} for i in range(90)]
    docs = {str(i): {"ho_mau_id": "same" if i < 2 else str(i)} for i in range(90)}
    requirements = [{"ca_id": str(i), "requirement_version_id": "VERSION"} for i in range(90)]
    chunks = [{"hop_dong_id": str(i)} for i in range(90)]
    first = split_cases(cases, requirements, chunks, [], docs)
    assert first == split_cases(cases, requirements, chunks, [], docs)
    assert first["0"] == first["1"]
    assert [list(first.values()).count(k) for k in ("DEV", "VALIDATION", "TEST")] == [60, 15, 15]
