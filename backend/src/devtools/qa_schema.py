"""Workbook QA tables, deliberately separate from mutable runtime module outputs."""

from devtools.database_schema import Table

QA_TABLES = (
    Table(
        "qa",
        "case_manifest",
        (
            ("case_id", "TEXT"),
            ("hop_dong_id", "TEXT"),
            ("group_id", "TEXT"),
            ("split", "TEXT"),
            ("case_kind", "TEXT"),
            ("label_quality", "TEXT"),
            ("dataset_version", "TEXT"),
            ("label_version", "TEXT"),
            ("knowledge_snapshot_sha256", "TEXT"),
            ("module_scope", "TEXT"),
            ("limitations_json", "JSONB"),
        ),
    ),
    Table(
        "qa",
        "artifacts",
        (
            ("artifact_part_id", "TEXT"),
            ("case_id", "TEXT"),
            ("role", "TEXT"),
            ("contract_name", "TEXT"),
            ("record_id", "TEXT"),
            ("part_number", "INTEGER"),
            ("part_count", "INTEGER"),
            ("payload_sha256", "TEXT"),
            ("content", "TEXT"),
        ),
    ),
    Table(
        "qa",
        "controlled_assertions",
        (
            ("case_id", "TEXT"),
            ("expected_assertions_json", "JSONB"),
            ("rationale", "TEXT"),
            ("legal_review_id", "TEXT"),
        ),
    ),
    Table(
        "qa",
        "legal_checks",
        (
            ("review_id", "TEXT"),
            ("document_number", "TEXT"),
            ("article_scope", "TEXT"),
            ("source_url", "TEXT"),
            ("source_sha256", "TEXT"),
            ("as_of", "DATE"),
            ("review_status", "TEXT"),
            ("finding_summary", "TEXT"),
            ("limitations", "TEXT"),
        ),
    ),
    Table(
        "qa",
        "source_checks",
        (
            ("tep_id", "TEXT"),
            ("hop_dong_id", "TEXT"),
            ("source_url", "TEXT"),
            ("status", "TEXT"),
            ("download_sha256", "TEXT"),
            ("bytes", "INTEGER"),
            ("error", "TEXT"),
        ),
    ),
    Table(
        "qa",
        "change_log",
        (
            ("change_id", "TEXT"),
            ("table_name", "TEXT"),
            ("record_id", "TEXT"),
            ("reason", "TEXT"),
            ("before_json", "JSONB"),
            ("after_json", "JSONB"),
        ),
    ),
)
QA_BY_NAME = {table.name: table for table in QA_TABLES}
QA_SHEETS = {"QA_" + table.name.upper(): table for table in QA_TABLES}
QA_GUIDES = frozenset({"QA_README", "QA_COVERAGE", "QA_TODO", "QA_SPLIT_SUMMARY"})
