"""Reference step 1–2 outputs for developing steps 3–4 before real DI output exists.

Dev/test only: business modules never import devtools. Payloads come from seeded QA
artifacts, so they are reference data, not output of a real parser/extractor.
"""

from legal_checker.core.postgres import connect_postgres
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import DocumentIntelligenceResult

from devtools.qa_validation import join_artifacts


def load_artifact(database_url: str, case_id: str, role: str, contract_name: str) -> dict:
    """Join one multipart QA payload; parts and SHA-256 are checked by join_artifacts."""
    with connect_postgres(database_url) as connection:
        rows = connection.execute(
            "SELECT * FROM qa.artifacts WHERE case_id=%s AND role=%s AND contract_name=%s",
            (case_id, role, contract_name),
        ).fetchall()
    payloads = join_artifacts(rows)
    if len(payloads) != 1:
        raise ValueError(
            f"{case_id}/{role}/{contract_name}: expected one payload, got {len(payloads)}"
        )
    return next(iter(payloads.values()))


def load_document(database_url: str, case_id: str) -> DocumentIntelligenceResult:
    """C02 profile, chunks and C03 citations of one case."""
    raw = load_artifact(database_url, case_id, "EXPECTED", "DocumentIntelligenceResult")
    return DocumentIntelligenceResult.model_validate(raw)


def load_context(database_url: str, case_id: str, run_id: str | None = None) -> Context:
    """Pinned case context; pass run_id so dev runs never reuse the reference run."""
    request = load_artifact(database_url, case_id, "INPUT", "PipelineRequest")
    fields = {name: request[name] for name in Context.model_fields}
    if run_id:
        fields["run_id"] = run_id
    return Context.model_validate(fields)


def list_cases(database_url: str, split: str = "DEV") -> list[str]:
    """Corpus case IDs of one split: DEV for tuning, VALIDATION only for final reports."""
    with connect_postgres(database_url) as connection:
        rows = connection.execute(
            "SELECT case_id FROM qa.case_manifest "
            "WHERE case_kind='CORPUS' AND split=%s ORDER BY case_id",
            (split,),
        ).fetchall()
    return [row["case_id"] for row in rows]
