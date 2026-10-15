from copy import deepcopy

import pytest
from devtools.database_schema import TABLES
from devtools.database_seed import SeedError, WorkbookSeed, read_workbook
from devtools.qa_schema import QA_TABLES
from devtools.qa_validation import join_artifacts, validate_qa
from seed_helpers import artifact, write_seed_workbook


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


def test_write_only_workbook_trailing_nulls_and_qa_roundtrip(tmp_path):
    seed = sample()
    path = tmp_path / "sample.xlsx"
    write_seed_workbook(seed, path)
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
