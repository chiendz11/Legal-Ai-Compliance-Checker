import os
import uuid
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import psycopg
import pytest
from legal_checker.core.config import Settings
from legal_checker.core.postgres import connect_postgres
from legal_checker.main import create_app
from legal_checker.migrations.manager import upgrade_database
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.shared.contracts.pipeline import PipelineRequest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo


@pytest.fixture
def app_factory(database_url):
    def build(*, settings=None, services=None):
        if settings is None:
            settings = replace(Settings.from_env(), database_url=database_url)
        return create_app(settings=settings, services=services)

    return build


@contextmanager
def isolated_database(*, initialize=True):
    base_url = os.environ.get("TEST_DATABASE_URL")
    if not base_url:
        pytest.skip("Set TEST_DATABASE_URL to run tests using PostgreSQL")
    if not conninfo_to_dict(base_url).get("dbname", "").startswith("legal_checker_test"):
        pytest.fail("TEST_DATABASE_URL dbname must start with legal_checker_test")
    name = "legal_checker_test_" + uuid.uuid4().hex
    admin_url = make_conninfo(base_url, dbname="postgres")
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = make_conninfo(base_url, dbname=name)
    try:
        if initialize:
            upgrade_database(url)
            with connect_postgres(url) as connection:
                connection.execute((Path(__file__).parent / "seed_knowledge.sql").read_text())
                connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
        yield url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture(scope="session")
def knowledge_database_url():
    with isolated_database() as url:
        yield url


@pytest.fixture
def database_url():
    with isolated_database() as url:
        yield url


@pytest.fixture
def empty_database_url():
    with isolated_database(initialize=False) as url:
        yield url


@pytest.fixture(scope="session")
def knowledge(knowledge_database_url):
    return Knowledge(knowledge_database_url)


def make_request(knowledge, version_id="PV_GYC005", finding="SATISFIED"):
    version = knowledge.versions[version_id]
    text = "Bằng chứng đã đối chiếu cho tiêu chí hiện tại."
    criteria = knowledge.criteria_for(version_id)
    data = {
        "ca_id": "CA_TEST",
        "phien_ban_id": "DEPLOY_TEST",
        "rule_version": "RULE_TEST",
        "legal_knowledge_version": "LEGAL_TEST",
        "knowledge_snapshot_sha256": knowledge.sha256,
        "run_id": "RUN_TEST",
        "trace_id": "TRACE_TEST",
        "payload": {
            "hop_dong_id": "HD_TEST",
            "requirements": [
                {
                    "yeu_cau_ca_id": "YCCA_TEST",
                    "ca_id": "CA_TEST",
                    "requirement_id": version["requirement_id"],
                    "requirement_version_id": version_id,
                    "scope_status": "MATCH",
                    "version_status": "RESOLVED",
                    "applicability_status": "CONFIRMED",
                    "moc_ap_dung": "2026-01-15",
                    "phien_ban_id": "DEPLOY_TEST",
                }
            ],
            "chunks": [
                {
                    "doan_id": "D_TEST",
                    "hop_dong_id": "HD_TEST",
                    "noi_dung": text,
                    "page_start": 1,
                    "page_end": 1,
                }
            ],
            "retrieval": [],
            "observations": [],
            "citations": [],
        },
    }
    for index, criterion in enumerate(criteria):
        cid = criterion["tieu_chi_id"]
        data["payload"]["retrieval"].append(
            {
                "truy_xuat_id": f"RTX_{index}",
                "yeu_cau_ca_id": "YCCA_TEST",
                "tieu_chi_id": cid,
                "doan_id": "D_TEST",
                "thu_hang": 1,
                "duoc_chon": True,
                "retrieval_version": "RET_TEST",
                "index_version": "IDX_TEST",
                "lan_chay_id": "RUN_TEST",
            }
        )
        data["payload"]["observations"].append(
            {
                "tieu_chi_id": cid,
                "proposed_finding": finding,
                "giai_thich": "Fixture observation",
                "gates": {
                    "coverage_complete": True,
                    "absence_verified": True,
                    "evidence_validated": True,
                    "source_verified": True,
                    "scope_confirmed": True,
                    "version_resolved": True,
                    "evidence_conflict": False,
                    "exceptions_resolved": True,
                },
                "evidence": [
                    {
                        "doan_id": "D_TEST",
                        "trich_dan": text,
                        "ky_tu_bat_dau": 0,
                        "ky_tu_ket_thuc": len(text),
                    }
                ],
                "local_applicability": "MATCH",
                "mandatory_confirmed": True,
                "all_pages_readable": True,
                "all_related_documents_received": True,
            }
        )
    return data


@pytest.fixture
def request_factory(knowledge):
    def build(version_id="PV_GYC005", finding="SATISFIED", mutate=None):
        data = deepcopy(make_request(knowledge, version_id, finding))
        if mutate:
            mutate(data)
        return PipelineRequest.model_validate(data)

    return build


@pytest.fixture
def response_factory():
    """Transport-only output for persistence tests, not a legal evaluation or reference."""
    from datetime import datetime, timezone

    from legal_checker.shared.contracts.pipeline import PipelineResponse, PipelineResult

    def build(request):
        return PipelineResponse(
            **request.model_dump(exclude={"contract_name", "payload"}),
            produced_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            payload=PipelineResult(
                criterion_results=[],
                requirement_results=[],
                risks=[],
                recommendations=[],
                excluded_requirements=[],
            ),
        )

    return build
