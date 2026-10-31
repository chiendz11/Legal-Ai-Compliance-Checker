"""Fresh installs, safe legacy handover and atomic Alembic upgrades on isolated DBs."""

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from legal_checker.core.config import BACKEND_ROOT
from legal_checker.core.postgres import connect_postgres
from legal_checker.migrations import manager
from legal_checker.migrations.manager import (
    MigrationAdoptionError,
    alembic_config,
    migration_engine,
    upgrade_database,
)
from legal_checker.migrations.schema_state import structure_fingerprints
from sqlalchemy import text

ROOT = files("legal_checker.migrations")
BASELINES = json.loads(ROOT.joinpath("legacy_baselines.json").read_text(encoding="utf-8"))


def legacy_database(database_url, version=3):
    """Recreate old persisted DDL/history without depending on the deleted old runner."""
    with connect_postgres(database_url) as connection:
        connection.execute("CREATE SCHEMA dev_meta")
        connection.execute("""
            CREATE TABLE dev_meta.schema_migrations (
                version INTEGER PRIMARY KEY, sha256 TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        for number in range(1, version + 1):
            entry = BASELINES[str(number)]
            connection.execute(ROOT.joinpath("sql", entry["sql_file"]).read_text(encoding="utf-8"))
            if number == 1:
                connection.execute("""
                    CREATE TABLE dev_meta.seed_imports (
                        source_sha256 TEXT PRIMARY KEY, row_counts JSONB NOT NULL,
                        imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """)
            connection.execute(
                "INSERT INTO dev_meta.schema_migrations VALUES (%s,%s,now())",
                (number, entry["sql_sha256"]),
            )
        connection.execute("INSERT INTO runtime.hop_dong (hop_dong_id) VALUES ('KEEP_ME')")
        connection.execute(
            "INSERT INTO dev_meta.seed_imports VALUES (%s,'{}'::jsonb,now())", ("a" * 64,)
        )


def current_revision(database_url):
    with connect_postgres(database_url) as connection:
        if not connection.execute(
            "SELECT to_regclass('dev_meta.alembic_version') AS name"
        ).fetchone()["name"]:
            return None
        return connection.execute("SELECT version_num FROM dev_meta.alembic_version").fetchone()[
            "version_num"
        ]


def test_fresh_upgrade_matches_frozen_schema_and_is_idempotent(empty_database_url):
    upgrade_database(empty_database_url)
    assert current_revision(empty_database_url) == "0003_qa"
    engine = migration_engine(empty_database_url)
    try:
        with engine.begin() as connection:
            assert structure_fingerprints(connection) == BASELINES["3"]["objects"]
            assert not connection.execute(
                text("SELECT to_regclass('dev_meta.schema_migrations')")
            ).scalar_one()
    finally:
        engine.dispose()
    with connect_postgres(empty_database_url) as connection:
        connection.execute("INSERT INTO runtime.hop_dong (hop_dong_id) VALUES ('KEEP_ME')")
    upgrade_database(empty_database_url)
    with connect_postgres(empty_database_url) as connection:
        assert connection.execute("SELECT count(*) AS n FROM runtime.hop_dong").fetchone()["n"] == 1


@pytest.mark.parametrize("version", [1, 2, 3])
def test_adopt_legacy_prefix_preserves_seeded_rows_and_history(empty_database_url, version):
    legacy_database(empty_database_url, version)
    upgrade_database(empty_database_url)
    assert current_revision(empty_database_url) == "0003_qa"
    with connect_postgres(empty_database_url) as connection:
        assert (
            connection.execute("SELECT hop_dong_id FROM runtime.hop_dong").fetchone()["hop_dong_id"]
            == "KEEP_ME"
        )
        assert (
            connection.execute("SELECT source_sha256 FROM dev_meta.seed_imports").fetchone()[
                "source_sha256"
            ]
            == "a" * 64
        )
        assert (
            connection.execute("SELECT count(*) AS n FROM dev_meta.schema_migrations").fetchone()[
                "n"
            ]
            == version
        )


@pytest.mark.parametrize(
    "change,match",
    [
        ("UPDATE dev_meta.schema_migrations SET sha256='bad' WHERE version=1", "checksum"),
        ("DELETE FROM dev_meta.schema_migrations WHERE version=1", "incomplete"),
        ("ALTER TABLE runtime.hop_dong ADD COLUMN untracked TEXT", "runtime.hop_dong"),
        (
            "ALTER TABLE knowledge.knowledge_snapshots ALTER COLUMN content DROP NOT NULL",
            "knowledge.knowledge_snapshots",
        ),
        (
            "ALTER TABLE runtime.hop_dong ALTER COLUMN hop_dong_id TYPE varchar(100)",
            "runtime.hop_dong",
        ),
        ("DROP INDEX qa.ix_qa_manifest_split", "qa.case_manifest"),
        ("ALTER TABLE qa.artifacts DISABLE TRIGGER immutable_qa_artifact", "qa.artifacts"),
    ],
)
def test_legacy_drift_is_rejected_without_stamp_or_row_loss(empty_database_url, change, match):
    legacy_database(empty_database_url)
    with connect_postgres(empty_database_url) as connection:
        connection.execute(change)
    with pytest.raises(MigrationAdoptionError, match=match):
        upgrade_database(empty_database_url)
    assert current_revision(empty_database_url) is None
    with connect_postgres(empty_database_url) as connection:
        assert (
            connection.execute("SELECT hop_dong_id FROM runtime.hop_dong").fetchone()["hop_dong_id"]
            == "KEEP_ME"
        )


def test_unversioned_existing_schema_is_not_blindly_stamped(empty_database_url):
    legacy_database(empty_database_url)
    with connect_postgres(empty_database_url) as connection:
        connection.execute("DROP TABLE dev_meta.schema_migrations")
    with pytest.raises(MigrationAdoptionError, match="unversioned"):
        upgrade_database(empty_database_url)
    assert current_revision(empty_database_url) is None


@pytest.mark.parametrize("tampered", [False, True])
def test_packaged_crlf_sql_keeps_frozen_checksum_and_rejects_edits(
    empty_database_url, tmp_path, monkeypatch, tampered
):
    legacy_database(empty_database_url)
    packaged = tmp_path / "packaged_migrations"
    shutil.copytree(str(ROOT), packaged)
    for baseline in BASELINES.values():
        path = packaged / "sql" / baseline["sql_file"]
        lf = path.read_bytes().replace(b"\r\n", b"\n")
        path.write_bytes(lf.replace(b"\n", b"\r\n"))
    if tampered:
        path.write_bytes(path.read_bytes() + b"-- changed packaged SQL\r\n")
    monkeypatch.setattr(manager, "files", lambda package: packaged)
    if tampered:
        with pytest.raises(MigrationAdoptionError, match="checksum"):
            upgrade_database(empty_database_url)
        assert current_revision(empty_database_url) is None
    else:
        upgrade_database(empty_database_url)
        assert current_revision(empty_database_url) == "0003_qa"
    with connect_postgres(empty_database_url) as connection:
        rows = connection.execute(
            "SELECT version, sha256 FROM dev_meta.schema_migrations ORDER BY version"
        ).fetchall()
        assert all(row["sha256"] == BASELINES[str(row["version"])]["sql_sha256"] for row in rows)
        assert (
            connection.execute("SELECT hop_dong_id FROM runtime.hop_dong").fetchone()["hop_dong_id"]
            == "KEEP_ME"
        )


def test_concurrent_init_uses_one_migration_history(empty_database_url):
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(upgrade_database, [empty_database_url] * 3))
    assert current_revision(empty_database_url) == "0003_qa"


def test_concurrent_cli_processes_serialize_upgrades(empty_database_url, tmp_path):
    def upgrade(_):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                str(BACKEND_ROOT / "alembic.ini"),
                "upgrade",
                "head",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": empty_database_url},
            timeout=30,
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(upgrade, range(3)))
    assert all(result.returncode == 0 for result in results), [r.stderr for r in results]
    assert current_revision(empty_database_url) == "0003_qa"


def test_failed_upgrade_rolls_back_ddl_and_revision(empty_database_url, tmp_path, monkeypatch):
    upgrade_database(empty_database_url)
    local = tmp_path / "migrations"
    shutil.copytree(str(ROOT), local)
    (local / "versions/0004_failure.py").write_text("""
from alembic import op
revision = "0004_failure"
down_revision = "0003_qa"
def upgrade():
    op.execute("ALTER TABLE runtime.hop_dong ADD COLUMN should_rollback TEXT")
    raise ValueError("simulated failure")
""")
    config = alembic_config()
    config.set_main_option("script_location", str(local))
    monkeypatch.setattr(manager, "alembic_config", lambda: config)
    with pytest.raises(ValueError, match="simulated failure"):
        upgrade_database(empty_database_url)
    assert current_revision(empty_database_url) == "0003_qa"
    with connect_postgres(empty_database_url) as connection:
        assert not connection.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='runtime' AND table_name='hop_dong' AND column_name='should_rollback'
        """).fetchone()


def test_cli_works_outside_repo_and_uses_environment_database(empty_database_url, tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(BACKEND_ROOT / "alembic.ini"),
            "upgrade",
            "head",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": empty_database_url},
    )
    assert result.returncode == 0, result.stderr
    assert current_revision(empty_database_url) == "0003_qa"


def test_revision_template_generates_valid_python_without_db(tmp_path):
    local = tmp_path / "migrations"
    shutil.copytree(str(ROOT), local)
    config = alembic_config()
    config.set_main_option("script_location", str(local))
    revision = command.revision(config, message="example change", rev_id="0004_example")
    assert revision.down_revision == "0003_qa"
    assert ScriptDirectory.from_config(config).get_current_head() == "0004_example"
    compile(open(revision.path).read(), revision.path, "exec")
