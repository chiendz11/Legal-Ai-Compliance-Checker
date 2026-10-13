"""Local PostgreSQL schema and workbook seed CLI. Run from repository root."""

import argparse
import json
import os
from pathlib import Path

import psycopg
from devtools.database_schema import TABLES
from devtools.database_seed import database_counts, migrate, read_workbook, seed_database
from dotenv import load_dotenv
from legal_checker.core.postgres import connect_postgres
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
    commands.add_parser("init", help="Create database if absent and apply versioned SQL migration")
    for command in ("seed", "preview"):
        child = commands.add_parser(command)
        child.add_argument("--workbook", type=Path, default=os.environ.get("SEED_WORKBOOK_PATH"))
    commands.add_parser("check", help="Show record counts and sample case IDs")
    args = parser.parse_args()
    if args.command == "init":
        database = conninfo_to_dict(args.database_url).get("dbname")
        if not database or database in ("postgres", "template0", "template1"):
            parser.error("Use a named application database, not postgres/template databases")
        with psycopg.connect(
            make_conninfo(args.database_url, dbname="postgres"), autocommit=True, connect_timeout=10
        ) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s", (database,)
            ).fetchone()
            if not exists:
                connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        with connect_postgres(args.database_url) as connection:
            connection.execute("SELECT pg_advisory_xact_lock(743249)")
            migrate(connection)
        print(f"Database {database}: migration ready, {len(TABLES)} tables")
    elif args.command in ("seed", "preview"):
        if args.workbook is None:
            parser.error("Provide --workbook or SEED_WORKBOOK_PATH in .env")
        seed = read_workbook(args.workbook)
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
            print(json.dumps(seed_database(args.database_url, seed), indent=2))
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
        print(
            json.dumps(
                {
                    "tables": counts,
                    "total_rows": sum(counts.values()),
                    "cases": cases,
                    "imports": imports,
                },
                indent=2,
                default=str,
            )
        )


if __name__ == "__main__":
    main()
