"""Read C07 inputs without changing the reference case, run or verification flags."""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import get_args
from uuid import uuid4

from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.compliance.mappers import map_chunk, map_requirement, map_retrieval
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository
from legal_checker.shared.contracts.document_intelligence import ContractProfile, ProfileFields
from legal_checker.shared.contracts.reasoning import ReasoningRequest


@contextmanager
def readonly_database():
    """Force connections opened in this synchronous CLI scope to default read-only.

    Keep other PGOPTIONS and restore the process environment on exit. This helper
    is for CLI composition, not concurrent application request middleware.
    """
    prior = os.environ.get("PGOPTIONS")
    os.environ["PGOPTIONS"] = ((prior + " ") if prior else "") + (
        "-c default_transaction_read_only=on"
    )
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop("PGOPTIONS", None)
        else:
            os.environ["PGOPTIONS"] = prior


def map_profile(row: dict | None, contract_id: str) -> ContractProfile:
    """Project nullable C02 fields; normalize bool storage, never mark them verified."""
    if row is not None and row.get("hop_dong_id") != contract_id:
        raise ValueError("C02 profile belongs to another contract")
    values = {}
    for name, field in ProfileFields.model_fields.items():
        value = (row or {}).get(name)
        if bool in get_args(field.annotation):
            if type(value) is not bool:
                value = {"true": True, "false": False}.get(
                    value.strip().lower() if isinstance(value, str) else ""
                )
        values[name] = value
    return ContractProfile(hop_dong_id=contract_id, profile=ProfileFields.model_validate(values))


@dataclass(frozen=True)
class LoadedC07Input:
    """Detached DEV input plus explicit lineage to the selected reference retrieval."""

    request: ReasoningRequest
    profile: ContractProfile
    lineage: dict
    read_only: bool


def fork_reference_request(reference: ReasoningRequest) -> tuple[ReasoningRequest, dict]:
    """Clone only existing selections into a new DEV run and retain source IDs."""
    data = reference.model_dump()
    data["run_id"] = f"{reference.ca_id}_C07_DEV_{uuid4().hex}"
    data["trace_id"] = str(uuid4())
    data["payload"]["observations"] = []
    if data["payload"]["external_evidence_registry"]:
        raise ValueError("Reference external registrations need new run-bound attestations")
    links = []
    for row in data["payload"]["retrieval"]:
        source_id = row["truy_xuat_id"]
        row["truy_xuat_id"] = "C06_DEV_" + uuid4().hex
        row["lan_chay_id"] = data["run_id"]
        links.append(
            {
                "source_truy_xuat_id": source_id,
                "dev_truy_xuat_id": row["truy_xuat_id"],
                "yeu_cau_ca_id": row["yeu_cau_ca_id"],
                "tieu_chi_id": row["tieu_chi_id"],
                "doan_id": row["doan_id"],
            }
        )
    return ReasoningRequest.model_validate(data), {
        "source_run_id": reference.run_id,
        "dev_run_id": data["run_id"],
        "retrieval": links,
        "selection_policy": "COPY_EXISTING_SELECTED_FINAL_ONLY",
    }


class C07InputRepository:
    """Compose existing retrieval reads and C02/snapshot lookups under read-only mode."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    def load(self, case_id: str, reference_run_id: str) -> LoadedC07Input:
        """Load all C05/chunks and selected FINAL C06, then detach a DEV request."""
        with readonly_database():
            with connect_postgres(self.database_url) as connection:
                status = connection.execute("SHOW transaction_read_only").fetchone()
                if status["transaction_read_only"] != "on":
                    raise ValueError("C07 repository requires a read-only database connection")
            repository = RetrievalDatasetRepository(self.database_url)
            source = repository.load_input_rows(case_id)
            rows = repository.load_seeded_evidence(case_id, reference_run_id)
            case = source["case"]
            with connect_postgres(self.database_url) as connection:
                manifest = connection.execute(
                    "SELECT knowledge_snapshot_sha256 FROM qa.case_manifest "
                    "WHERE case_id=%s AND hop_dong_id=%s",
                    (case_id, case["hop_dong_id"]),
                ).fetchone()
                profile = connection.execute(
                    "SELECT * FROM runtime.ho_so_hop_dong WHERE hop_dong_id=%s",
                    (case["hop_dong_id"],),
                ).fetchone()
        if not manifest or not manifest["knowledge_snapshot_sha256"]:
            raise ValueError("Case has no pinned knowledge snapshot")
        reference = ReasoningRequest(
            ca_id=case["ca_id"],
            phien_ban_id=case["phien_ban_id"],
            rule_version=case["rule_version"],
            legal_knowledge_version=case["legal_knowledge_version"],
            knowledge_snapshot_sha256=manifest["knowledge_snapshot_sha256"],
            run_id=reference_run_id,
            trace_id=str(uuid4()),
            payload={
                "hop_dong_id": case["hop_dong_id"],
                "requirements": [map_requirement(row) for row in source["requirements"]],
                "chunks": [map_chunk(row) for row in source["chunks"]],
                "retrieval": [
                    map_retrieval(row)
                    for row in rows
                    if row["duoc_chon"] is True and row["giai_doan"] == "FINAL"
                ],
            },
        )
        request, lineage = fork_reference_request(reference)
        lineage["profile_context"] = "C02_FIELDS_UNVERIFIED"
        lineage["raw_c06_count"] = len(rows)
        return LoadedC07Input(request, map_profile(profile, case["hop_dong_id"]), lineage, True)
