"""Audit is independent of providers and never retains request bodies or error messages."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from legal_checker.shared.contracts.audit import LlmAudit
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.llm.audit import (
    AuditPersistenceError,
    AuditResultMissingError,
    PostgresLlmAuditSink,
    audit_llm_call,
    payload_sha256,
)
from pydantic import ValidationError


def event_data(**changes):
    return {
        "lan_goi_id": "CALL_TEST",
        "ca_id": "CA_TEST",
        "module": "COMPLIANCE",
        "provider": "LOCAL",
        "model_version": "test-model",
        "prompt_version": "prompt-v1",
        "schema_version": "Proposal/1.0",
        "input_sha256": "a" * 64,
        "output_sha256": "b" * 64,
        "latency_ms": 10,
        "trang_thai": "SUCCESS",
        "so_lan_thu": 1,
        "trace_id": "TRACE_TEST",
        "ngay_goi": datetime(2026, 1, 1, tzinfo=timezone.utc),
        **changes,
    }


class MemorySink:
    def __init__(self):
        self.events = []

    def append(self, event):
        self.events.append(event.model_copy(deep=True))


def call_args(**changes):
    return {
        "context": Context(
            ca_id="CA_TEST",
            run_id="RUN_TEST",
            trace_id="TRACE_TEST",
            phien_ban_id="DEPLOY_TEST",
            rule_version="RULE_TEST",
            legal_knowledge_version="LEGAL_TEST",
            knowledge_snapshot_sha256="a" * 64,
        ),
        "module": "COMPLIANCE",
        "provider": "LOCAL",
        "model_version": "test-model",
        "prompt_version": "prompt-v1",
        "schema_version": "Proposal/1.0",
        "input_payload": {"messages": [{"content": "PRIVATE_CONTRACT_TEXT"}]},
        **changes,
    }


def test_payload_hash_is_reproducible_and_preserves_source_text():
    assert payload_sha256({"a": 1, "b": "Tiếng Việt"}) == payload_sha256(
        {"b": "Tiếng Việt", "a": 1}
    )
    assert payload_sha256("Tiếng Việt") == payload_sha256("Tiếng Việt".encode())
    assert payload_sha256(" text ") != payload_sha256("text")
    with pytest.raises(ValueError):
        payload_sha256({"invalid": float("nan")})


@pytest.mark.parametrize(
    "changes",
    [
        {"ca_id": " "},
        {"input_sha256": "not-a-hash"},
        {"output_sha256": "bad"},
        {"output_sha256": None},
        {"trang_thai": "ERROR"},
        {"ma_loi": "RATE_LIMIT"},
        {"trang_thai": "ERROR", "ma_loi": "Error: api_key=SECRET"},
        {"input_tokens": -1},
        {"output_tokens": True},
        {"latency_ms": -1},
        {"so_lan_thu": 0},
        {"ngay_goi": datetime(2026, 1, 1)},
        {"chi_phi": Decimal("-1"), "don_vi_tien": "USD"},
        {"chi_phi": Decimal("0.01")},
        {"chi_phi": Decimal("NaN")},
        {"api_key": "DO_NOT_STORE_SECRETS"},
        {"raw_prompt": "PRIVATE"},
    ],
)
def test_invalid_metadata_is_rejected(changes):
    with pytest.raises(ValidationError):
        LlmAudit.model_validate(event_data(**changes))


def test_mutated_events_are_validated_before_connecting():
    bad = LlmAudit(**event_data()).model_copy(update={"input_sha256": "bad"})
    with pytest.raises(ValidationError):
        PostgresLlmAuditSink("postgresql://invalid/never_connected").append(bad)


def test_success_has_real_usage_and_hashes_without_raw_payloads():
    sink = MemorySink()
    output = {"answer": "PRIVATE_RESULT"}
    with audit_llm_call(sink, **call_args()) as call:
        call.complete(
            output, input_tokens=12, output_tokens=3, cost=Decimal("0.0012"), currency="USD"
        )
    event = sink.events[0]
    assert event.trang_thai == "SUCCESS"
    assert event.ma_loi is None
    assert event.output_sha256 == payload_sha256(output)
    assert event.input_sha256 == payload_sha256(call_args()["input_payload"])
    assert event.input_tokens == 12 and event.output_tokens == 3
    assert event.chi_phi == Decimal("0.0012")
    assert event.latency_ms >= 0 and event.ngay_goi.utcoffset().total_seconds() == 0
    assert "PRIVATE" not in event.model_dump_json()


def test_unreported_usage_and_cost_remain_null():
    sink = MemorySink()
    with audit_llm_call(sink, **call_args()) as call:
        call.complete("actual output")
    event = sink.events[0]
    assert event.input_tokens is event.output_tokens is event.chi_phi is None


def test_actual_returned_model_can_replace_requested_alias_without_extra_call():
    sink = MemorySink()
    with audit_llm_call(sink, **call_args(model_version="requested-alias")) as call:
        call.complete("actual output", model_version="actual-model-snapshot")
    assert len(sink.events) == 1
    assert sink.events[0].model_version == "actual-model-snapshot"


def test_provider_error_is_recorded_without_copying_its_message():
    sink = MemorySink()
    error = RuntimeError("api_key=PRIVATE_SECRET; provider body PRIVATE_TEXT")
    with pytest.raises(RuntimeError) as caught, audit_llm_call(sink, **call_args()):
        raise error
    assert caught.value is error
    event = sink.events[0]
    assert event.trang_thai == "ERROR" and event.ma_loi == "PROVIDER_ERROR"
    assert event.output_sha256 is None and event.output_tokens is None
    assert "PRIVATE" not in event.model_dump_json()


def test_missing_result_never_becomes_a_fake_success():
    sink = MemorySink()
    with pytest.raises(AuditResultMissingError), audit_llm_call(sink, **call_args()):
        pass
    assert sink.events[0].trang_thai == "ERROR"
    assert sink.events[0].ma_loi == "RESULT_NOT_RECORDED"


def test_separate_provider_attempts_have_separate_ids():
    sink = MemorySink()
    with pytest.raises(TimeoutError), audit_llm_call(sink, **call_args(attempt=1)):
        raise TimeoutError("private SDK error")
    with audit_llm_call(sink, **call_args(attempt=2)) as call:
        call.complete("response")
    assert [e.so_lan_thu for e in sink.events] == [1, 2]
    assert len({e.lan_goi_id for e in sink.events}) == 2
    assert len({e.trace_id for e in sink.events}) == 1


class BrokenSink:
    def append(self, event):
        raise OSError("private database error")


def test_audit_write_failure_after_success_exposes_metadata_for_re_delivery():
    provider_calls = []
    with pytest.raises(AuditPersistenceError) as caught:
        with audit_llm_call(BrokenSink(), **call_args()) as call:
            provider_calls.append(1)
            call.complete("actual response")
    assert provider_calls == [1]  # Audit never retries the provider call.
    assert caught.value.event.trang_thai == "SUCCESS"
    sink = MemorySink()
    sink.append(caught.value.event)
    assert len(sink.events) == 1


def test_audit_write_failure_does_not_replace_primary_provider_error():
    error = TimeoutError("private provider error")
    with pytest.raises(TimeoutError) as caught, audit_llm_call(BrokenSink(), **call_args()):
        raise error
    assert caught.value is error
    assert "audit persistence also failed" in caught.value.__notes__[0]
    assert "database" not in caught.value.__notes__[0]


def test_module_can_map_a_provider_error_to_a_safe_code():
    sink = MemorySink()
    with pytest.raises(TimeoutError), audit_llm_call(sink, **call_args()) as call:
        call.set_error_code("RATE_LIMIT")
        raise TimeoutError("private SDK response")
    assert sink.events[0].ma_loi == "RATE_LIMIT"
    assert sink.events[0].lan_goi_id == call.call_id


def test_raw_error_text_cannot_be_used_as_a_code():
    sink = MemorySink()
    with pytest.raises(ValidationError), audit_llm_call(sink, **call_args()) as call:
        call.set_error_code("HTTP 401 Authorization: Bearer PRIVATE_KEY")
    assert sink.events[0].ma_loi == "PROVIDER_ERROR"
    assert "PRIVATE_KEY" not in sink.events[0].model_dump_json()
