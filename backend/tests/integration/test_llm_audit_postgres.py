"""X02 roundtrip and duplicate/conflict behavior on a disposable PostgreSQL DB."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
import pytest
from legal_checker.api.dependencies import build_services
from legal_checker.core.config import Settings
from legal_checker.core.exceptions import ConflictError
from legal_checker.core.postgres import connect_postgres
from legal_checker.shared.contracts.audit import LlmAudit
from legal_checker.shared.llm.audit import PostgresLlmAuditSink


@pytest.fixture
def audit_sink(database_url):
    with connect_postgres(database_url) as connection:
        connection.execute("INSERT INTO runtime.hop_dong (hop_dong_id) VALUES ('HD_AUDIT')")
        connection.execute(
            "INSERT INTO runtime.ca_danh_gia (ca_id, hop_dong_id) VALUES ('CA_AUDIT', 'HD_AUDIT')"
        )
    return PostgresLlmAuditSink(database_url)


def event(**changes):
    return LlmAudit.model_validate(
        {
            "lan_goi_id": "CALL_TEST",
            "ca_id": "CA_AUDIT",
            "module": "DOCUMENTS",
            "provider": "LOCAL",
            "model_version": "test-model",
            "prompt_version": "profile-v1",
            "schema_version": "Profile/1.0",
            "input_sha256": "a" * 64,
            "output_sha256": "b" * 64,
            "input_tokens": 12,
            "output_tokens": 4,
            "latency_ms": 42,
            "chi_phi": Decimal("0.0000123"),
            "don_vi_tien": "USD",
            "trang_thai": "SUCCESS",
            "so_lan_thu": 1,
            "trace_id": "TRACE_AUDIT",
            "ngay_goi": datetime(2026, 1, 1, tzinfo=timezone.utc),
            **changes,
        }
    )


def test_roundtrip_idempotency_and_case_scoped_read(audit_sink, database_url):
    original = event()
    audit_sink.append(original)
    audit_sink.append(original)
    assert audit_sink.get("CA_AUDIT", original.lan_goi_id) == original
    assert audit_sink.get("FOREIGN_CASE", original.lan_goi_id) is None
    with connect_postgres(database_url) as connection:
        rows = connection.execute("SELECT loai_du_lieu FROM runtime.nhat_ky_goi_llm").fetchall()
        assert rows == [{"loai_du_lieu": "LIVE_LLM_CALL"}]


def test_changed_call_id_conflicts_and_never_overwrites(audit_sink):
    original = event()
    audit_sink.append(original)
    with pytest.raises(ConflictError):
        audit_sink.append(event(output_sha256="c" * 64))
    assert audit_sink.get(original.ca_id, original.lan_goi_id) == original


def test_concurrent_identical_delivery_is_idempotent(audit_sink, database_url):
    original = event()
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: audit_sink.append(original), range(4)))
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM runtime.nhat_ky_goi_llm").fetchone()["n"]
            == 1
        )


def test_error_unknown_usage_and_unregistered_case(audit_sink, database_url):
    original = event(
        trang_thai="ERROR",
        ma_loi="PROVIDER_ERROR",
        output_sha256=None,
        input_tokens=None,
        output_tokens=None,
        chi_phi=None,
        don_vi_tien=None,
    )
    audit_sink.append(original)
    assert audit_sink.get(original.ca_id, original.lan_goi_id) == original
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        audit_sink.append(event(lan_goi_id="UNKNOWN_CASE_CALL", ca_id="NO_CASE"))
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM runtime.nhat_ky_goi_llm").fetchone()["n"]
            == 1
        )


def test_dependency_factory_provides_shared_sink_without_provider_configuration(database_url):
    services = build_services(Settings(database_url=database_url))
    assert isinstance(services.llm_audit, PostgresLlmAuditSink)
    with connect_postgres(database_url) as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM runtime.nhat_ky_goi_llm").fetchone()["n"]
            == 0
        )
