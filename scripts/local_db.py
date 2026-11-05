"""Local PostgreSQL schema and workbook seed CLI. Run from repository root."""

import argparse
import json
import os
from pathlib import Path

import psycopg
from devtools.database_schema import TABLES
from devtools.database_seed import database_counts, read_workbook, seed_database
from devtools.database_update import update_database
from dotenv import load_dotenv
from legal_checker.core.postgres import connect_postgres
from legal_checker.migrations.manager import upgrade_database
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

DEFAULT_DATABASE_URL = (
    "postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_dev"
)


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url", default=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create database if absent and upgrade Alembic to head")
    for command in ("seed", "preview"):
        child = commands.add_parser(command)
        child.add_argument("--workbook", type=Path, default=os.environ.get("SEED_WORKBOOK_PATH"))
    update = commands.add_parser(
        "update", help="Upgrade matching baseline rows; preserve run history"
    )
    update.add_argument("--previous-workbook", type=Path, required=True)
    update.add_argument("--workbook", type=Path, default=os.environ.get("SEED_WORKBOOK_PATH"))
    update.add_argument("--legal-knowledge-version")
    update.add_argument("--knowledge-snapshot-sha256")
    update.add_argument("--dry-run", action="store_true", help="Plan in a rolled-back transaction")
    commands.add_parser("check", help="Show record counts and sample case IDs")
    args = parser.parse_args()
    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "configs/dataset_dev_validation.json").read_text()
    )
    if args.command == "init":
        database = conninfo_to_dict(args.database_url).get("dbname")
        if not database or database in ("postgres", "template0", "template1"):
            parser.error("Use a named application database, not postgres/template databases")
        with psycopg.connect(
            make_conninfo(args.database_url, dbname="postgres"),
            autocommit=True,
            connect_timeout=10,
        ) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s", (database,)
            ).fetchone()
            if not exists:
                connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        upgrade_database(args.database_url)
        print(f"Database {database}: Alembic head ready, {len(TABLES)} workbook tables")
    elif args.command in ("seed", "preview"):
        if args.workbook is None:
            parser.error("Provide --workbook or SEED_WORKBOOK_PATH in .env")
        seed = read_workbook(args.workbook)
        pinned = manifest if args.workbook.name == manifest["workbook"] else {}
        if pinned and seed.source_sha256 != pinned["required_files"][pinned["workbook"]]:
            parser.error("Workbook checksum differs from the pinned release")
        if args.command == "preview":
            print(
                json.dumps(
                    {
                        "source_sha256": seed.source_sha256,
                        "tables": seed.counts,
                        "qa_tables": seed.qa_counts,
                    },
                    indent=2,
                )
            )
        else:
            print(
                json.dumps(
                    seed_database(
                        args.database_url,
                        seed,
                        reviewed_knowledge_sha256=(
                            pinned.get("knowledge_snapshot_sha256")
                            if pinned.get("review_revision")
                            else None
                        ),
                    ),
                    indent=2,
                )
            )
    elif args.command == "update":
        if args.workbook is None:
            parser.error("Provide --workbook or SEED_WORKBOOK_PATH in .env")
        pinned = manifest if args.workbook.name == manifest["workbook"] else {}
        version = args.legal_knowledge_version or pinned.get("legal_knowledge_version")
        if not version:
            parser.error("Provide --legal-knowledge-version or use the pinned release workbook")
        result = update_database(
            args.database_url,
            args.previous_workbook,
            args.workbook,
            legal_knowledge_version=version,
            expected_knowledge_sha256=(
                args.knowledge_snapshot_sha256 or pinned.get("knowledge_snapshot_sha256")
            ),
            dry_run=args.dry_run,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        counts = database_counts(args.database_url)
        with connect_postgres(args.database_url) as connection:
            cases = connection.execute("""
                SELECT ca_id, hop_dong_id, trang_thai, loai_du_lieu
                FROM runtime.ca_danh_gia ORDER BY ca_id
            """).fetchall()
            imports = connection.execute("""
                SELECT source_sha256, imported_at FROM dev_meta.seed_imports
            """).fetchall()
            updates = connection.execute("""
                SELECT previous_source_sha256,source_sha256,knowledge_snapshot_sha256,
                       legal_knowledge_version,applied_at
                FROM dev_meta.dataset_updates ORDER BY sequence
            """).fetchall()
        print(
            json.dumps(
                {
                    "tables": counts,
                    "total_rows": sum(counts.values()),
                    "cases": cases,
                    "imports": imports,
                    "updates": updates,
                },
                indent=2,
                default=str,
            )
        )


if __name__ == "__main__":
    main()
