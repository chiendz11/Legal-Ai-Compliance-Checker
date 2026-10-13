"""Actual PostgreSQL integration. Isolated databases, never the developer's DB."""

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
import pytest
from devtools.database_schema import BY_NAME, TABLES
from devtools.database_seed import SeedError, WorkbookSeed, database_counts, seed_database
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.legal_knowledge.postgres_repository import WorkbookKnowledgeRepository
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo


@pytest.fixture
def database_url():
    base_url = os.environ.get("TEST_DATABASE_URL")
    if not base_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    base_name = conninfo_to_dict(base_url).get("dbname", "")
    if not base_name.startswith("legal_checker_test"):
        pytest.fail("TEST_DATABASE_URL dbname must start with legal_checker_test")
    test_name = "legal_checker_test_" + uuid.uuid4().hex
    admin_url = make_conninfo(base_url, dbname="postgres")
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(test_name)))
    try:
        yield make_conninfo(base_url, dbname=test_name)
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(test_name))
            )


@pytest.fixture
def seed():
    """Two cases/runs with closed references; no copy of private workbook data."""
    seed = WorkbookSeed("a" * 64, {table.name: [] for table in TABLES})

    def add(table_name, **values):
        row = {name: None for name, _ in BY_NAME[table_name].columns}
        row.update(values)
        seed.tables[table_name].append(row)

    add("yeu_cau_phap_ly", requirement_id="REQ-1", ten_nhom_yeu_cau="Yêu cầu mẫu")
    add("phien_ban_yeu_cau", requirement_version_id="VER-1", requirement_id="REQ-1")
    add(
        "tieu_chi_danh_gia",
        tieu_chi_id="CRIT-1",
        requirement_version_id="VER-1",
        thu_tu=1,
        human_verified=False,
        dieu_kien={"status": "UNKNOWN"},
    )
    add(
        "quy_tac_quyet_dinh",
        quy_tac_id="RULE-1",
        tieu_chi_id="CRIT-1",
        uu_tien=100,
        finding="UNKNOWN",
        dieu_kien_json={"status": "UNKNOWN"},
    )
    for number in (1, 2):
        doc, case, requirement, chunk = (
            f"DOC-{number}",
            f"CASE-{number}",
            f"APPL-{number}",
            f"CHUNK-{number}",
        )
        add(
            "hop_dong",
            hop_dong_id=doc,
            ten_tai_lieu=f"Hợp đồng mẫu {number}",
            loai_du_lieu="SYNTHETIC_DEMO",
        )
        add(
            "ho_so_hop_dong",
            hop_dong_id=doc,
            la_hop_dong_theo_mau="UNKNOWN",
            gia_tri_hop_dong=Decimal("1234.56"),
            la_nha_o_xa_hoi=False,
        )
        add(
            "ca_danh_gia",
            ca_id=case,
            hop_dong_id=doc,
            profile_snapshot_json={"human_verified": False, "status": "UNKNOWN"},
            ngay_danh_gia=datetime(2026, 10, 10, tzinfo=timezone.utc),
        )
        add(
            "yeu_cau_ap_dung",
            yeu_cau_ca_id=requirement,
            ca_id=case,
            requirement_id="REQ-1",
            requirement_version_id="VER-1",
        )
        add(
            "doan_hop_dong",
            doan_id=chunk,
            hop_dong_id=doc,
            thu_tu=1,
            noi_dung=f"Nội dung riêng {number}",
            page_start=1,
            page_end=1,
        )
        for run in ("RUN-1", "RUN-2"):
            add(
                "ket_qua_truy_xuat",
                truy_xuat_id=f"EVID-{number}-{run}",
                yeu_cau_ca_id=requirement,
                doan_id=chunk,
                lan_chay_id=run,
                tieu_chi_id="CRIT-1",
                thu_hang=1,
                duoc_chon=True,
            )
    return seed


def test_seed_idempotent_and_preserves_developer_changes(database_url, seed):
    first = seed_database(database_url, seed)
    assert first["inserted"] == sum(seed.counts.values())
    before = database_counts(database_url)
    with connect_postgres(database_url) as connection:
        connection.execute(
            "UPDATE runtime.hop_dong SET ten_tai_lieu='Dev edit' WHERE hop_dong_id='DOC-1'"
        )
        connection.execute("INSERT INTO runtime.hop_dong (hop_dong_id) VALUES ('DOC-DEV')")
    second = seed_database(database_url, seed)
    assert second["status"] == "already_seeded"
    assert second["inserted"] == 0
    after = database_counts(database_url)
    assert after["runtime.hop_dong"] == before["runtime.hop_dong"] + 1
    with connect_postgres(database_url) as connection:
        row = connection.execute(
            "SELECT ten_tai_lieu FROM runtime.hop_dong WHERE hop_dong_id='DOC-1'"
        ).fetchone()
        assert row["ten_tai_lieu"] == "Dev edit"


def test_sql_roundtrip_preserves_source_types_and_status(database_url, seed):
    seed_database(database_url, seed)
    with connect_postgres(database_url) as connection:
        profile = connection.execute(
            "SELECT * FROM runtime.ho_so_hop_dong WHERE hop_dong_id='DOC-1'"
        ).fetchone()
        assert profile["gia_tri_hop_dong"] == Decimal("1234.56")
        assert profile["la_hop_dong_theo_mau"] == "UNKNOWN"
        assert profile["la_nha_o_xa_hoi"] is False
        case = connection.execute(
            "SELECT * FROM runtime.ca_danh_gia WHERE ca_id='CASE-1'"
        ).fetchone()
        assert case["profile_snapshot_json"] == {"human_verified": False, "status": "UNKNOWN"}
        assert case["ngay_danh_gia"] == datetime(2026, 10, 10, tzinfo=timezone.utc)


def test_failed_seed_rolls_back_schema_and_all_rows(database_url, seed):
    # FKs are valid, but PostgreSQL's INTEGER bound rejects this value during insertion.
    seed.tables["doan_hop_dong"][0]["thu_tu"] = 2**40
    with pytest.raises(psycopg.errors.NumericValueOutOfRange):
        seed_database(database_url, seed)
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute("SELECT to_regnamespace('runtime') AS schema").fetchone()["schema"]
            is None
        )
        assert (
            connection.execute("SELECT to_regnamespace('dev_meta') AS schema").fetchone()["schema"]
            is None
        )


def test_seed_preserves_rows_already_in_initialized_database(database_url, seed):
    from devtools.database_seed import migrate

    with connect_postgres(database_url) as connection:
        migrate(connection)
        connection.execute(
            "INSERT INTO runtime.hop_dong (hop_dong_id, ten_tai_lieu) "
            "VALUES ('DOC-1', 'Prior edit')"
        )
    result = seed_database(database_url, seed)
    assert result["skipped_existing"] == 1
    with connect_postgres(database_url) as connection:
        row = connection.execute(
            "SELECT ten_tai_lieu FROM runtime.hop_dong WHERE hop_dong_id='DOC-1'"
        ).fetchone()
        assert row["ten_tai_lieu"] == "Prior edit"


def test_changed_workbook_is_rejected_without_data_loss(database_url, seed):
    seed_database(database_url, seed)
    before = database_counts(database_url)
    seed.source_sha256 = "b" * 64
    with pytest.raises(SeedError, match="Different workbook"):
        seed_database(database_url, seed)
    assert database_counts(database_url) == before


def test_sql_rejects_orphan_and_workbook_rejects_cross_contract_evidence(database_url, seed):
    seed_database(database_url, seed)
    with (
        pytest.raises(psycopg.errors.ForeignKeyViolation),
        connect_postgres(database_url) as connection,
    ):
        connection.execute("INSERT INTO runtime.ho_so_hop_dong (hop_dong_id) VALUES ('NO-DOC')")
    seed.tables["ket_qua_truy_xuat"][0]["doan_id"] = "CHUNK-2"
    with pytest.raises(SeedError, match="different contract"):
        seed_database(database_url, seed)


def test_repository_isolates_case_and_run_and_joins_knowledge(database_url, seed):
    seed_database(database_url, seed)
    repository = RetrievalDatasetRepository(database_url)
    inputs = repository.load_input_rows("CASE-1")
    assert [row["doan_id"] for row in inputs["chunks"]] == ["CHUNK-1"]
    assert [row["yeu_cau_ca_id"] for row in inputs["requirements"]] == ["APPL-1"]
    assert [row["tieu_chi_id"] for row in inputs["criteria"]] == ["CRIT-1"]
    evidence = repository.load_seeded_evidence("CASE-1", "RUN-2")
    assert [row["truy_xuat_id"] for row in evidence] == ["EVID-1-RUN-2"]
    assert evidence[0]["noi_dung"] == "Nội dung riêng 1"
    with pytest.raises(KeyError):
        repository.load_input_rows("NO-CASE")
    knowledge = WorkbookKnowledgeRepository(database_url)
    assert knowledge.criteria_for("VER-1")[0]["human_verified"] is False
    assert knowledge.decision_rules_for("CRIT-1")[0]["finding"] == "UNKNOWN"
