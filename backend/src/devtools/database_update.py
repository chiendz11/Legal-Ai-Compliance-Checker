"""Guarded workbook updates: preserve uploads, historical runs and immutable snapshots.

The previous workbook is the expected baseline, not permission to overwrite changes.
Only matching baseline records may change. QA payloads are reference data, while any
outputs registered to a real run and case pins remain untouched. No LLM calls occur.
"""

import hashlib
import json
from pathlib import Path

from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.legal_knowledge.repository import TABLE_KEYS, canonical
from psycopg import sql
from psycopg.types.json import Jsonb

from devtools.database_schema import TABLES
from devtools.database_seed import SeedError
from devtools.qa_schema import QA_SHEETS
from devtools.qa_validation import join_artifacts
from devtools.workbook_stream import StreamWorkbook

PROTECTED_TABLES = (
    "workflow_runs",
    "report_versions",
    "review_events",
    "assessment_runs",
    "assessment_output_lineage",
    "assessment_case_pins",
    "nhat_ky_review",
    "nhat_ky_goi_llm",
    "app_users",
)
QA_FREEZE_TRIGGERS = {
    "case_manifest": "immutable_case_manifest",
    "artifacts": "immutable_qa_artifact",
    "controlled_assertions": "immutable_controlled_assertion",
}


def _history(connection):
    result = {}
    for name in PROTECTED_TABLES:
        result[name] = connection.execute(
            sql.SQL("""SELECT count(*) AS count,
                md5(coalesce(string_agg(h,'' ORDER BY h),'')) AS digest
                FROM (SELECT md5(to_jsonb(t)::text) h FROM {} t) records""").format(
                sql.Identifier("runtime", name)
            )
        ).fetchone()
    return result


def _capture_knowledge(connection):
    tables = {
        name: connection.execute(
            sql.SQL("SELECT * FROM {} ORDER BY {}").format(
                sql.Identifier("knowledge", name), sql.Identifier(key)
            )
        ).fetchall()
        for name, key in TABLE_KEYS.items()
    }
    # Match Knowledge's Python ordering, independent of the server's collation.
    for name, key in TABLE_KEYS.items():
        tables[name].sort(key=lambda row, pk=key: row[pk])
    content = json.loads(canonical({"schema_version": "v7.4.9", "tables": tables}))
    return hashlib.sha256(canonical(content).encode()).hexdigest(), content


def _projection(table, alias):
    return sql.SQL("ROW({})").format(
        sql.SQL(",").join(sql.Identifier(alias, name) for name, _ in table.columns)
    )


def _protected(table, alias="t"):
    if table.schema != "runtime":
        return sql.SQL("FALSE")
    clauses = [
        sql.SQL("""EXISTS(SELECT 1 FROM runtime.assessment_output_lineage l
            WHERE l.table_name IN ({},{}) AND l.output_id={}::text)""").format(
            sql.Literal(table.name),
            sql.Literal("runtime." + table.name),
            sql.Identifier(alias, table.primary_key),
        )
    ]
    if table.name == "ca_danh_gia":
        clauses.append(
            sql.SQL("""EXISTS(SELECT 1 FROM runtime.workflow_runs w WHERE w.ca_id={})
                OR EXISTS(SELECT 1 FROM runtime.assessment_case_pins p WHERE p.ca_id={})""").format(
                sql.Identifier(alias, table.primary_key), sql.Identifier(alias, table.primary_key)
            )
        )
    if table.name == "bao_cao_danh_gia":
        clauses.append(
            sql.SQL("EXISTS(SELECT 1 FROM runtime.report_versions r WHERE r.bao_cao_id={})").format(
                sql.Identifier(alias, table.primary_key)
            )
        )
    return sql.SQL("({})").format(sql.SQL(" OR ").join(clauses))


def _stage(connection, book, sheet, table, label):
    temporary = "_dataset_" + label + "_" + table.name
    columns = [name for name, _ in table.columns]
    connection.execute(
        sql.SQL("CREATE TEMP TABLE {} ON COMMIT DROP AS SELECT {} FROM {} WITH NO DATA").format(
            sql.Identifier(temporary),
            sql.SQL(",").join(map(sql.Identifier, columns)),
            sql.Identifier(table.schema, table.name),
        )
    )
    parts = []
    current = None
    count = 0
    with connection.cursor().copy(
        sql.SQL("COPY {} ({}) FROM STDIN").format(
            sql.Identifier(temporary), sql.SQL(",").join(map(sql.Identifier, columns))
        )
    ) as writer:
        for record in book.records(sheet, table):
            if not record[table.primary_key]:
                raise SeedError(f"Empty primary key in {sheet}")
            if table.name == "artifacts":
                key = tuple(record[k] for k in ("case_id", "role", "contract_name", "record_id"))
                if parts and key != current:
                    raise SeedError("Non-contiguous or incomplete QA artifact")
                current = key
                parts.append(record)
                if record["part_number"] == record["part_count"]:
                    join_artifacts(parts)
                    parts = []
            writer.write_row(
                [
                    Jsonb(record[name])
                    if kind == "JSONB" and record[name] is not None
                    else record[name]
                    for name, kind in table.columns
                ]
            )
            count += 1
    if parts:
        raise SeedError("Incomplete QA artifact")
    connection.execute(
        sql.SQL("ALTER TABLE {} ADD PRIMARY KEY ({})").format(
            sql.Identifier(temporary), sql.Identifier(table.primary_key)
        )
    )
    return temporary, count


def _apply_table(connection, table, old, new):
    target = sql.Identifier(table.schema, table.name)
    key = sql.Identifier(table.primary_key)
    protected = _protected(table)
    old_row, new_row, current = (_projection(table, a) for a in ("o", "n", "t"))
    conflicts = connection.execute(
        sql.SQL("""SELECT t.{} AS id FROM {} t JOIN {} o USING ({})
            LEFT JOIN {} n USING ({})
            WHERE NOT {} AND {} IS DISTINCT FROM {}
              AND (n.{} IS NULL OR {} IS DISTINCT FROM {}) LIMIT 10""").format(
            key,
            target,
            sql.Identifier(old),
            key,
            sql.Identifier(new),
            key,
            protected,
            current,
            old_row,
            key,
            current,
            new_row,
        )
    ).fetchall()
    collisions = connection.execute(
        sql.SQL("""SELECT t.{} AS id FROM {} t JOIN {} n USING ({})
            LEFT JOIN {} o USING ({}) WHERE o.{} IS NULL
            AND NOT {} AND {} IS DISTINCT FROM {} LIMIT 10""").format(
            key,
            target,
            sql.Identifier(new),
            key,
            sql.Identifier(old),
            key,
            key,
            protected,
            current,
            new_row,
        )
    ).fetchall()
    if conflicts or collisions:
        raise SeedError(
            f"Preserved developer changes in {table.schema}.{table.name}; "
            f"conflicting IDs: {[row['id'] for row in conflicts + collisions]}"
        )
    missing = connection.execute(
        sql.SQL("""SELECT count(*) n FROM {} o LEFT JOIN {} t USING ({})
            WHERE t.{} IS NULL""").format(sql.Identifier(old), target, key, key)
    ).fetchone()["n"]
    if missing:
        raise SeedError(f"Baseline rows were removed from {table.schema}.{table.name}")
    removed = connection.execute(
        sql.SQL("SELECT count(*) n FROM {} o LEFT JOIN {} n USING ({}) WHERE n.{} IS NULL").format(
            sql.Identifier(old), sql.Identifier(new), key, key
        )
    ).fetchone()["n"]
    if removed and table.schema != "qa":
        raise SeedError(f"Business row deletion is not allowed: {table.name}")
    # Curating a new checksum-pinned release is the sole controlled exception to
    # frozen QA references. ALTER acquires an exclusive table lock; restoration
    # belongs to this same transaction, including dry-run/error rollbacks.
    trigger = QA_FREEZE_TRIGGERS.get(table.name) if table.schema == "qa" else None
    if trigger:
        connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
        connection.execute(
            sql.SQL("ALTER TABLE {} DISABLE TRIGGER {}").format(target, sql.Identifier(trigger))
        )
    skipped = connection.execute(
        sql.SQL("""SELECT count(*) n FROM {} t JOIN {} n USING ({})
            WHERE {} AND {} IS DISTINCT FROM {}""").format(
            target, sql.Identifier(new), key, protected, current, new_row
        )
    ).fetchone()["n"]
    sets = sql.SQL(",").join(
        sql.SQL("{}=n.{}").format(sql.Identifier(name), sql.Identifier(name))
        for name, _ in table.columns
        if name != table.primary_key
    )
    updated = connection.execute(
        sql.SQL("""UPDATE {} t SET {} FROM {} n
            WHERE t.{}=n.{} AND NOT {} AND {} IS DISTINCT FROM {}""").format(
            target, sets, sql.Identifier(new), key, key, protected, current, new_row
        )
    ).rowcount
    columns = sql.SQL(",").join(sql.Identifier(name) for name, _ in table.columns)
    selected = sql.SQL(",").join(sql.Identifier("n", name) for name, _ in table.columns)
    inserted = connection.execute(
        sql.SQL(
            "INSERT INTO {} ({}) SELECT {} FROM {} n LEFT JOIN {} t USING ({}) WHERE t.{} IS NULL"
        ).format(target, columns, selected, sql.Identifier(new), target, key, key)
    ).rowcount
    deleted = 0
    if removed:
        deleted = connection.execute(
            sql.SQL("""DELETE FROM {} t USING {} o WHERE t.{}=o.{}
                AND NOT EXISTS(SELECT 1 FROM {} n WHERE n.{}=t.{})""").format(
                target, sql.Identifier(old), key, key, sql.Identifier(new), key, key
            )
        ).rowcount
    if trigger:
        # New/removed multipart rows queue deferred FK events. Flush them before
        # ALTER TABLE; PostgreSQL rejects DDL while such events are pending.
        connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
        connection.execute(
            sql.SQL("ALTER TABLE {} ENABLE TRIGGER {}").format(target, sql.Identifier(trigger))
        )
        connection.execute("SET CONSTRAINTS ALL DEFERRED")
    return {"updated": updated, "inserted": inserted, "deleted": deleted, "protected": skipped}


def update_database(
    database_url: str,
    previous_workbook: Path,
    workbook: Path,
    *,
    legal_knowledge_version: str,
    expected_knowledge_sha256: str | None = None,
    dry_run: bool = False,
    progress=None,
):
    """Apply one audited release atomically; caller upgrades Alembic explicitly first."""
    with StreamWorkbook(previous_workbook) as before, StreamWorkbook(workbook) as after:
        if before.sha256 == after.sha256:
            raise SeedError("Update requires two different workbook revisions")
        with connect_postgres(database_url) as connection:
            with connection.transaction(force_rollback=dry_run):
                connection.execute("SELECT pg_advisory_xact_lock(743249)")
                if not connection.execute(
                    "SELECT to_regclass('dev_meta.dataset_updates') name"
                ).fetchone()["name"]:
                    raise SeedError("Run scripts.local_db init to install the data-update ledger")
                applied = connection.execute(
                    "SELECT summary FROM dev_meta.dataset_updates WHERE source_sha256=%s",
                    (after.sha256,),
                ).fetchone()
                if applied:
                    return {**applied["summary"], "status": "already_applied"}
                latest = connection.execute(
                    "SELECT source_sha256 FROM dev_meta.dataset_updates "
                    "ORDER BY sequence DESC LIMIT 1"
                ).fetchone()
                imported = connection.execute(
                    "SELECT source_sha256 FROM dev_meta.seed_imports"
                ).fetchall()
                active = (
                    latest["source_sha256"]
                    if latest
                    else (imported[0]["source_sha256"] if len(imported) == 1 else None)
                )
                if active != before.sha256:
                    raise SeedError("Previous workbook does not match the database release")
                connection.execute("SET LOCAL lock_timeout='15s'")
                connection.execute("LOCK TABLE runtime.workflow_runs IN SHARE MODE")
                if connection.execute(
                    "SELECT count(*) n FROM runtime.workflow_runs "
                    "WHERE status IN ('QUEUED','RUNNING')"
                ).fetchone()["n"]:
                    raise SeedError("Wait until queued/running assessments finish before updating")
                protected_before = _history(connection)
                old_hash, old_snapshot = _capture_knowledge(connection)
                connection.execute(
                    """INSERT INTO knowledge.knowledge_snapshots(sha256,schema_version,content)
                        VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (old_hash, "v7.4.9", Jsonb(old_snapshot)),
                )
                updates = {}
                tables = [(t.name, t) for t in TABLES] + list(QA_SHEETS.items())
                for sheet, table in tables:
                    if sheet not in before.sheets or sheet not in after.sheets:
                        raise SeedError(f"Missing worksheet {sheet}")
                    if before.crc(sheet) == after.crc(sheet):
                        continue
                    if progress:
                        progress(f"Staging {table.schema}.{table.name}")
                    old, old_count = _stage(connection, before, sheet, table, "old")
                    new, new_count = _stage(connection, after, sheet, table, "new")
                    updates[f"{table.schema}.{table.name}"] = {
                        **_apply_table(connection, table, old, new),
                        "previous_rows": old_count,
                        "source_rows": new_count,
                    }
                    connection.execute(
                        sql.SQL("DROP TABLE {},{}").format(sql.Identifier(old), sql.Identifier(new))
                    )
                new_hash, content = _capture_knowledge(connection)
                if expected_knowledge_sha256 and new_hash != expected_knowledge_sha256:
                    raise SeedError("Updated knowledge differs from the pinned release hash")
                for name in ("tieu_chi_danh_gia", "quy_tac_quyet_dinh", "ngoai_le_ap_dung"):
                    if any(r.get("human_verified") is not True for r in content["tables"][name]):
                        raise SeedError("This update must use the user-reviewed knowledge release")
                connection.execute(
                    """INSERT INTO knowledge.knowledge_snapshots
                        (sha256,schema_version,content,review_status)
                        VALUES (%s,%s,%s,'HUMAN_VERIFIED') ON CONFLICT DO NOTHING""",
                    (new_hash, "v7.4.9", Jsonb(content)),
                )
                snapshot = connection.execute(
                    "SELECT review_status FROM knowledge.knowledge_snapshots WHERE sha256=%s",
                    (new_hash,),
                ).fetchone()
                if snapshot["review_status"] != "HUMAN_VERIFIED":
                    raise SeedError("Existing immutable snapshot lacks reviewed release metadata")
                connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
                if _history(connection) != protected_before:
                    raise SeedError("Historical runs/reports/reviews changed; update rolled back")
                summary = {
                    "status": "dry_run" if dry_run else "updated",
                    "previous_source_sha256": before.sha256,
                    "source_sha256": after.sha256,
                    "previous_knowledge_snapshot_sha256": old_hash,
                    "knowledge_snapshot_sha256": new_hash,
                    "legal_knowledge_version": legal_knowledge_version,
                    "tables": updates,
                    "protected_history": protected_before,
                }
                connection.execute(
                    """INSERT INTO dev_meta.dataset_updates
                        (previous_source_sha256,source_sha256,knowledge_snapshot_sha256,
                         legal_knowledge_version,summary) VALUES (%s,%s,%s,%s,%s)""",
                    (
                        before.sha256,
                        after.sha256,
                        new_hash,
                        legal_knowledge_version,
                        Jsonb(summary),
                    ),
                )
                return summary
