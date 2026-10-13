"""QA stays separate from runtime; serialized inputs and frozen assertions survive SQL."""

import psycopg
import pytest
from devtools.database_schema import TABLES
from devtools.database_seed import WorkbookSeed, seed_database
from devtools.qa_schema import QA_TABLES
from devtools.qa_validation import join_artifacts
from devtools.workbook_optimization import artifact
from legal_checker.core.postgres import connect_postgres


def qa_seed():
    seed = WorkbookSeed("b" * 64, {t.name: [] for t in TABLES}, {t.name: [] for t in QA_TABLES})
    seed.qa_tables["case_manifest"].append(
        {
            "case_id": "QA_ONLY",
            "hop_dong_id": "SYNTHETIC_DOC",
            "group_id": "QA_ONLY",
            "split": "REGRESSION",
            "case_kind": "CONTROLLED",
            "label_quality": "SYNTHETIC_SPEC",
            "dataset_version": "test",
            "label_version": "SPEC_V1",
            "knowledge_snapshot_sha256": "c" * 64,
            "module_scope": "C05-C11",
            "limitations_json": {"synthetic": True, "legal_gold": False},
        }
    )
    seed.qa_tables["controlled_assertions"].append(
        {
            "case_id": "QA_ONLY",
            "expected_assertions_json": {"requirement_statuses": ["INSUFFICIENT"]},
            "rationale": "Independent behavior specification",
            "legal_review_id": None,
        }
    )
    artifact(
        seed.qa_tables, "QA_ONLY", "INPUT", "ExampleInput", "QA_ONLY", {"text": "Đầu vào " * 5000}
    )
    return seed


def test_qa_seed_roundtrip_and_no_runtime_case_pollution(database_url):
    seed = qa_seed()
    first = seed_database(database_url, seed)
    assert first["qa_inserted"] == sum(seed.qa_counts.values())
    assert seed_database(database_url, seed)["status"] == "already_seeded"
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM runtime.ca_danh_gia").fetchone()["n"] == 0
        )
        rows = connection.execute("SELECT * FROM qa.artifacts").fetchall()
        assert next(iter(join_artifacts(rows).values())) == {"text": "Đầu vào " * 5000}
        row = connection.execute("SELECT * FROM qa.case_manifest").fetchone()
        assert row["limitations_json"] == {"synthetic": True, "legal_gold": False}


@pytest.mark.parametrize("table", ["case_manifest", "artifacts", "controlled_assertions"])
def test_reference_rows_reject_changes(database_url, table):
    seed_database(database_url, qa_seed())
    with pytest.raises(psycopg.errors.RaiseException), connect_postgres(database_url) as connection:
        connection.execute("DELETE FROM qa." + table)
