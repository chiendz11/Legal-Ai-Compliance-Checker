"""Bounded-memory import of large, inline-string release workbooks.

Business FKs, QA identities and multipart checks are enforced in the same
transaction. This path does not retain the entire reference corpus in RAM.
"""

from pathlib import Path

from legal_checker.core.postgres import connect_postgres
from legal_checker.migrations.manager import upgrade_database
from psycopg.types.json import Jsonb

from devtools.database_schema import BY_NAME, GUIDE_SHEETS, TABLES
from devtools.database_seed import (
    SeedError,
    _pin_snapshot,
    insert_table,
    restore_case_review_context,
)
from devtools.qa_schema import QA_GUIDES, QA_SHEETS, QA_TABLES
from devtools.qa_validation import join_artifacts
from devtools.workbook_stream import StreamWorkbook


def seed_large_workbook(
    database_url: str,
    path: Path,
    *,
    expected_source_sha256: str | None = None,
    expected_knowledge_sha256: str | None = None,
    knowledge_review_status: str = "DEV_UNVERIFIED",
) -> dict:
    with StreamWorkbook(path) as workbook:
        if expected_source_sha256 and workbook.sha256 != expected_source_sha256:
            raise SeedError("Workbook checksum differs from the pinned release")
        unknown = set(workbook.sheets) - set(BY_NAME) - set(QA_SHEETS) - GUIDE_SHEETS - QA_GUIDES
        if unknown or not set(BY_NAME).issubset(workbook.sheets):
            raise SeedError("Workbook has missing or unknown sheets")
        upgrade_database(database_url)
        with connect_postgres(database_url) as connection:
            connection.execute("SELECT pg_advisory_xact_lock(743249)")
            imports = connection.execute(
                "SELECT source_sha256 FROM dev_meta.seed_imports"
            ).fetchall()
            updates = connection.execute(
                "SELECT source_sha256 FROM dev_meta.dataset_updates ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            if updates:
                if updates["source_sha256"] != workbook.sha256:
                    raise SeedError("Database has a different release; use a fresh local DB")
                return {"status": "already_seeded", "inserted": 0, "streaming": True}
            if imports:
                if any(r["source_sha256"] != workbook.sha256 for r in imports):
                    raise SeedError(
                        "Different workbook already seeded. Use a separate fresh local DB"
                    )
                return {"status": "already_seeded", "inserted": 0, "streaming": True}

            counts = {}
            manifests = {}
            splits = {}
            parts = []
            active_payload = None
            seen_payloads = set()
            runtime_cases = {}
            qa_present = any(name in workbook.sheets for name in QA_SHEETS)
            if qa_present and not set(QA_SHEETS).issubset(workbook.sheets):
                raise SeedError("Incomplete QA sheet set")

            for table in (*TABLES, *(QA_TABLES if qa_present else ())):
                sheet = "QA_" + table.name.upper() if table.schema == "qa" else table.name
                batch = []
                total = 0
                if table.schema == "qa" and table.name == "case_manifest":
                    runtime_cases = {
                        r["ca_id"]: r["hop_dong_id"]
                        for r in connection.execute(
                            "SELECT ca_id,hop_dong_id FROM runtime.ca_danh_gia"
                        ).fetchall()
                    }
                for row in workbook.records(sheet, table):
                    if not row[table.primary_key]:
                        raise SeedError(f"Empty primary key in {sheet}")
                    if table.schema == "qa":
                        if table.name == "case_manifest":
                            if (
                                row["split"] not in {"DEV", "VALIDATION", "TEST", "REGRESSION"}
                                or row["case_kind"] not in {"CORPUS", "CONTROLLED"}
                                or row["label_quality"]
                                not in {"SILVER_GUARD_REFERENCE", "SYNTHETIC_SPEC"}
                            ):
                                raise SeedError("Invalid QA manifest classification")
                            if row["case_id"] in manifests:
                                raise SeedError("Duplicate QA case identity")
                            if (
                                row["case_kind"] == "CORPUS"
                                and runtime_cases.get(row["case_id"]) != row["hop_dong_id"]
                            ):
                                raise SeedError(
                                    "QA corpus case references a foreign runtime contract"
                                )
                            group = row["group_id"]
                            if group in splits and splits[group] != row["split"]:
                                raise SeedError("A document family crosses QA splits")
                            splits[group] = row["split"]
                            manifests[row["case_id"]] = row
                        if table.name in {"artifacts", "controlled_assertions"}:
                            if row["case_id"] not in manifests:
                                raise SeedError("QA record references an unknown case")
                        if table.name == "artifacts":
                            if row["role"] not in {"INPUT", "EXPECTED", "PROPOSAL"}:
                                raise SeedError("Invalid QA artifact role")
                            key = tuple(
                                row[k] for k in ("case_id", "role", "contract_name", "record_id")
                            )
                            if not parts:
                                if key in seen_payloads:
                                    raise SeedError("QA payload repeats after its final part")
                                active_payload = key
                            elif active_payload != key:
                                raise SeedError("Large-workbook QA multipart rows must be grouped")
                            parts.append(row)
                            if row["part_number"] == row["part_count"]:
                                join_artifacts(parts)
                                seen_payloads.add(key)
                                parts = []
                    batch.append(row)
                    if len(batch) == 128:
                        inserted = insert_table(connection, table, batch)
                        if inserted != len(batch):
                            raise SeedError(f"Duplicate keys or existing rows in {sheet}")
                        total += inserted
                        batch = []
                if table.name == "artifacts" and parts:
                    raise SeedError("Incomplete QA multipart payload")
                if batch:
                    inserted = insert_table(connection, table, batch)
                    if inserted != len(batch):
                        raise SeedError(f"Duplicate keys or existing rows in {sheet}")
                    total += inserted
                counts[sheet] = total
            connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
            restore_case_review_context(connection)
            if expected_knowledge_sha256:
                _pin_snapshot(connection, expected_knowledge_sha256, knowledge_review_status)
            connection.execute(
                "INSERT INTO dev_meta.seed_imports VALUES (%s, %s, now())",
                (workbook.sha256, Jsonb(counts)),
            )
            return {
                "status": "seeded",
                "streaming": True,
                "source_sha256": workbook.sha256,
                "inserted": sum(counts.values()),
                "tables": counts,
                "knowledge_snapshot_sha256": expected_knowledge_sha256,
                "knowledge_review_status": knowledge_review_status,
            }
