"""Provider-independent X02 audit. No LLM client, prompt storage or secret handling."""

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from time import perf_counter
from typing import Any, Protocol
from uuid import uuid4

from psycopg import sql
from pydantic import BaseModel

from legal_checker.core.exceptions import ConflictError
from legal_checker.core.postgres import connect_postgres
from legal_checker.shared.contracts.audit import LlmAudit
from legal_checker.shared.contracts.common import Context


class LlmAuditSink(Protocol):
    def append(self, event: LlmAudit) -> None: ...


def payload_sha256(value: Any) -> str:
    """Hash text/bytes exactly, or a canonical JSON payload; never retain the payload."""
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        raw = value.encode("utf-8")
    else:
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
        raw = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class PostgresLlmAuditSink:
    """Insert-only writer. Identical re-delivery is safe; changed call IDs conflict."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    def append(self, event: LlmAudit) -> None:
        # Revalidate mutable/model_copy-created events before opening a transaction.
        values = LlmAudit.model_validate(event.model_dump()).model_dump()
        values["loai_du_lieu"] = "LIVE_LLM_CALL"
        columns = sql.SQL(", ").join(map(sql.Identifier, values))
        with connect_postgres(self.database_url) as connection:
            inserted = connection.execute(
                sql.SQL(
                    "INSERT INTO runtime.nhat_ky_goi_llm ({}) VALUES ({}) "
                    "ON CONFLICT (lan_goi_id) DO NOTHING RETURNING lan_goi_id"
                ).format(columns, sql.SQL(", ").join(sql.Placeholder() for _ in values)),
                tuple(values.values()),
            ).fetchone()
            if inserted is None:
                prior = connection.execute(
                    sql.SQL("SELECT {} FROM runtime.nhat_ky_goi_llm WHERE lan_goi_id=%s").format(
                        columns
                    ),
                    (event.lan_goi_id,),
                ).fetchone()
                if prior is None or dict(prior) != values:
                    raise ConflictError("LLM audit call ID already has different contents")

    def get(self, ca_id: str, lan_goi_id: str) -> LlmAudit | None:
        columns = sql.SQL(", ").join(map(sql.Identifier, LlmAudit.model_fields))
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(
                sql.SQL(
                    "SELECT {} FROM runtime.nhat_ky_goi_llm WHERE ca_id=%s AND lan_goi_id=%s"
                ).format(columns),
                (ca_id, lan_goi_id),
            ).fetchone()
        return LlmAudit.model_validate(row) if row else None


class AuditResultMissingError(RuntimeError):
    """A caller left the audit scope without recording the actual provider result."""


class AuditPersistenceError(RuntimeError):
    """Provider succeeded but persistence failed; retry append(event), not the LLM call."""

    def __init__(self, event: LlmAudit):
        super().__init__("LLM call completed but its audit could not be persisted")
        self.event = event.model_copy(deep=True)


class LlmCall:
    """One provider attempt. Only metadata and hashes are kept in memory."""

    def __init__(self, event: LlmAudit):
        self._event = event
        self._completed = False
        self._error_code = "PROVIDER_ERROR"

    @property
    def call_id(self) -> str:
        return self._event.lan_goi_id

    def set_error_code(self, code: str) -> None:
        """Use a safe module-mapped code in an SDK exception handler, never its message."""
        LlmAudit.model_validate({**self._event.model_dump(), "trang_thai": "ERROR", "ma_loi": code})
        self._error_code = code

    def complete(
        self,
        output: Any,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost: Decimal | None = None,
        currency: str | None = None,
    ) -> None:
        """Record the actual returned payload and reported usage; no legal interpretation."""
        if self._completed:
            raise RuntimeError("Provider result already recorded for this attempt")
        self._event = LlmAudit.model_validate(
            {
                **self._event.model_dump(),
                "trang_thai": "SUCCESS",
                "ma_loi": None,
                "output_sha256": payload_sha256(output),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "chi_phi": cost,
                "don_vi_tien": currency,
            }
        )
        self._completed = True

    def _finish(self, started: float, error_code: str | None = None) -> LlmAudit:
        changes = {"latency_ms": max(0, int((perf_counter() - started) * 1000))}
        if error_code:
            changes.update(trang_thai="ERROR", ma_loi=error_code)
        return LlmAudit.model_validate({**self._event.model_dump(), **changes})


@contextmanager
def audit_llm_call(
    sink: LlmAuditSink,
    *,
    context: Context,
    module: str,
    provider: str,
    model_version: str,
    prompt_version: str,
    schema_version: str,
    input_payload: Any,
    attempt: int = 1,
):
    """Wrap one actual provider attempt, then persist success/failure on a separate connection.

    Call complete() immediately after the SDK returns. Keep business reasoning outside
    this scope. SDK retries must be accounted for by the module; no provider is called here.
    """
    call = LlmCall(
        LlmAudit(
            lan_goi_id="LLM_" + uuid4().hex,
            ca_id=context.ca_id,
            module=module,
            provider=provider,
            model_version=model_version,
            prompt_version=prompt_version,
            schema_version=schema_version,
            input_sha256=payload_sha256(input_payload),
            latency_ms=0,
            trang_thai="ERROR",
            ma_loi="PROVIDER_ERROR",
            so_lan_thu=attempt,
            trace_id=context.trace_id,
            ngay_goi=datetime.now(timezone.utc),
        )
    )
    started = perf_counter()
    try:
        yield call
        if not call._completed:
            raise AuditResultMissingError("Call complete() with the actual provider output")
    except BaseException as error:
        code = (
            "RESULT_NOT_RECORDED"
            if isinstance(error, AuditResultMissingError)
            else call._error_code
        )
        event = call._finish(started, code)
        try:
            sink.append(event)
        except Exception:
            # Preserve the primary provider/module error without exposing secondary DB details.
            error.add_note("LLM audit persistence also failed; no saved audit is guaranteed.")
        raise
    else:
        event = call._finish(started)
        try:
            sink.append(event)
        except Exception as error:
            raise AuditPersistenceError(event) from error
