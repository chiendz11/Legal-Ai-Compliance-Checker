"""Run/replay C07 -> C08 -> C10 -> C11 offline; opt in to transactional persistence.

Read mode exports the exact saved run without evaluating any business module.
This CLI does not instantiate a paid provider. Use the C07 runner separately for
explicitly authorized live calls, then replay its analyses and independent reviews.
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from legal_checker.core.config import Settings
from legal_checker.modules.assessments.audit import digest
from legal_checker.modules.assessments.integrity import validate_membership
from legal_checker.modules.assessments.repository import OUTPUTS, Store
from legal_checker.modules.compliance.input_repository import C07InputRepository, readonly_database
from legal_checker.modules.compliance.llm_contracts import CriterionAnalysis
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.modules.compliance.reviewed_observations import BackendReview
from legal_checker.modules.compliance.run_c07 import (
    read_json,
    read_models,
    run_assessment,
)
from legal_checker.modules.compliance.verification import CriterionVerification
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import ContractProfile
from legal_checker.shared.contracts.pipeline import PipelineRequest, PipelineResponse
from legal_checker.shared.contracts.reasoning import (
    ExternalEvidenceRegistration,
    ReasoningPayload,
    ReasoningRequest,
)


def write_json(path: Path, value) -> None:
    """Keep artifact bytes stable across PostgreSQL JSONB key normalization."""
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def run_pipeline(request, knowledge, *, store=None) -> PipelineResponse:
    """Injected persistence is optional; the workflow itself remains pure."""
    from legal_checker.workflows.steps_5_7 import evaluate

    response = evaluate(request, knowledge)
    return store.save(request, response) if store is not None else response


def export_run(output: Path, request, response, metadata, *, lineage=None):
    """Never overwrite an earlier handoff package; preserve all DTOs and their hashes."""
    request = PipelineRequest.model_validate(request.model_dump())
    response = PipelineResponse.model_validate(response.model_dump())
    validate_membership(request, response)
    if metadata.get("db_results_saved") is True and lineage is None:
        raise ValueError("Saved export requires exact output lineage")
    if lineage is not None:
        expected = {
            (table, getattr(row, key)): row.model_dump(mode="json")
            for table, (attribute, key) in OUTPUTS.items()
            for row in getattr(response.payload, attribute)
        }
        actual = {}
        for row in lineage:
            key = (row["table_name"], row["output_id"])
            if row["ca_id"] != request.ca_id or row["run_id"] != request.run_id or key in actual:
                raise ValueError("Export lineage case/run/membership mismatch")
            actual[key] = row["payload"]
        if actual != expected:
            raise ValueError("Export lineage differs from saved output DTOs")
    if output.exists():
        raise FileExistsError("Output directory already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Build all artifacts beside the destination, then publish the complete folder.
    # A failed write leaves no partial package at the requested output location.
    with TemporaryDirectory(prefix=f".{output.name}.", dir=output.parent) as temporary:
        staged = Path(temporary)
        metadata = _write_export(staged, request, response, metadata, lineage=lineage)
        if output.exists():
            raise FileExistsError("Output directory appeared during export")
        staged.rename(output)
    return metadata


def _write_export(output, request, response, metadata, *, lineage):
    write_json(output / "input.json", request.model_dump(mode="json"))
    write_json(output / "output.json", response.model_dump(mode="json"))
    for filename, name in (
        ("c07", "criterion_results"),
        ("c08", "requirement_results"),
        ("c10", "risks"),
        ("c11", "recommendations"),
    ):
        write_json(
            output / f"{filename}.json",
            [item.model_dump(mode="json") for item in getattr(response.payload, name)],
        )
    write_json(output / "diagnostics.json", response.payload.diagnostics)
    write_json(
        output / "citations.json",
        [row.model_dump(mode="json") for row in request.payload.citations],
    )
    write_json(
        output / "registry.json",
        [row.model_dump(mode="json") for row in request.payload.external_evidence_registry],
    )
    provenance = request.payload.reasoning_provenance
    if "analyses" in provenance:
        for name in ("analyses", "reviews", "verifications"):
            write_json(output / f"{name}.json", provenance.get(name, []))
        write_json(output / "profile.json", provenance.get("profile"))
    if lineage is not None:
        write_json(output / "lineage.json", lineage)
    metadata = {
        **metadata,
        "case_id": request.ca_id,
        "contract_id": request.payload.hop_dong_id,
        "run_id": request.run_id,
        "knowledge_snapshot_sha256": request.knowledge_snapshot_sha256,
        "produced_at_utc": response.produced_at.isoformat(),
        "input_sha256": digest(request),
        "output_sha256": digest(response),
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "c05": len(request.payload.requirements),
            "c06": len(request.payload.retrieval),
            "c07": len(response.payload.criterion_results),
            "c08": len(response.payload.requirement_results),
            "c09": len(request.payload.citations),
            "c10": len(response.payload.risks),
            "c11": len(response.payload.recommendations),
        },
        "findings": dict(Counter(item.finding for item in response.payload.criterion_results)),
        "requirement_statuses": dict(
            Counter(item.status for item in response.payload.requirement_results)
        ),
        "risk_types": dict(Counter(item.risk_type for item in response.payload.risks)),
        "citation_branch_status": request.payload.citation_branch_status
        or ("COMPLETED" if request.payload.citations else "NOT_RUN"),
        "analysis_origins": dict(
            Counter(row.get("origin", "UNSPECIFIED") for row in provenance.get("analyses", []))
        ),
        "paid_api_attempts": 0,
        "expert_quality_validation": False,
        "review_status": "PENDING",
    }
    write_json(output / "metadata.json", metadata)
    report = [
        "# Kết quả nhóm C",
        "",
        f"Case `{request.ca_id}`, run `{request.run_id}`; mode `{metadata['mode']}`.",
        "",
        f"Counts: `{json.dumps(metadata['counts'], ensure_ascii=False)}`.",
        f"Findings: `{json.dumps(metadata['findings'])}`.",
        f"C08: `{json.dumps(metadata['requirement_statuses'])}`.",
        f"Đã lưu DB: `{metadata['db_results_saved']}`.",
        "",
        "`input.json` và `output.json` là DTO đầy đủ. `diagnostics.json` giữ knowledge gaps",
        "và trạng thái citation. `lineage.json` (khi lưu/đọc DB) ghi membership đúng case/run.",
        "",
        "Lần chạy này không gọi API trả phí; knowledge và kết quả vẫn chờ review.",
        "Demo dùng upstream tham chiếu không đo chất lượng pháp lý hoặc chất lượng OCR/retrieval.",
    ]
    (output / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return metadata


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", help="Case ID; defaults to CA360_001 for reference/read mode")
    parser.add_argument("--reference-run", help="C05/C06 upstream run, only in reference mode")
    parser.add_argument("--input", type=Path, help="Saved Steps57Input or CriterionReasoningInput")
    parser.add_argument("--profile", type=Path)
    parser.add_argument(
        "--citations", type=Path, help="Actual C09 list bound to the input case/run"
    )
    parser.add_argument("--citations-completed", action="store_true")
    parser.add_argument("--replay-analyses", type=Path)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--verifications", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--read-run", help="Read this exact stored run without recomputation")
    parser.add_argument("--output-dir", type=Path)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.read_run is not None and any(
        (
            args.input,
            args.save,
            args.replay_analyses,
            args.reviews,
            args.verifications,
            args.registry,
            args.profile,
            args.citations,
            args.citations_completed,
            args.reference_run,
        )
    ):
        parser.error("--read-run only accepts --case and --output-dir")
    if args.replay_analyses and not args.input:
        parser.error("--replay-analyses requires --input to preserve proposal/review bindings")
    if args.reviews and not args.replay_analyses:
        parser.error("--reviews requires --replay-analyses; no approval is generated offline")
    if args.input and args.reference_run:
        parser.error("--reference-run cannot be combined with --input")
    if args.input and not args.replay_analyses and (args.profile or args.verifications):
        parser.error("--profile/--verifications with --input require --replay-analyses")
    for name in ("case", "reference_run", "read_run"):
        value = getattr(args, name)
        if value is not None and not value.strip():
            parser.error("--" + name.replace("_", "-") + " cannot be empty")
    case_id = args.case or "CA360_001"
    output = args.output_dir or Path("outputs/group_c_runs") / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:12]
    )
    if output.exists():
        parser.error("--output-dir must be new; existing artifacts are immutable")
    try:
        settings = Settings.from_env()
        store = Store(settings.database_url) if args.save or args.read_run else None
        if args.read_run:
            with readonly_database():
                response = store.get(case_id, args.read_run)
                request = store.get_input(case_id, args.read_run)
                lineage = store.get_lineage(case_id, args.read_run)
            if request is None or response is None:
                raise ValueError("Requested saved case/run was not found")
            if request.ca_id != case_id or request.run_id != args.read_run:
                raise ValueError("Saved input belongs to another case/run")
            metadata = {"mode": "READ_SAVED", "db_results_saved": True, "recomputed": False}
        else:
            profile = None
            with readonly_database():
                if args.input:
                    source = read_json(args.input)
                    if source.get("contract_name") == "Steps57Input":
                        request = PipelineRequest.model_validate(source)
                        source_lineage = {"input_file": str(args.input), "policy": "PRESERVED"}
                    else:
                        reasoning = ReasoningRequest.model_validate(source)
                        request = PipelineRequest(
                            **reasoning.model_dump(include=set(Context.model_fields)),
                            payload=reasoning.payload.model_dump(),
                        )
                        source_lineage = {"input_file": str(args.input), "policy": "C07_REPLAY"}
                    if args.case is not None and request.ca_id != args.case:
                        raise ValueError("--case differs from the input case")
                else:
                    loaded = C07InputRepository(settings.database_url).load(
                        case_id, args.reference_run or case_id + "_PDF360_LS2_REFERENCE"
                    )
                    profile = loaded.profile
                    request = PipelineRequest(
                        **loaded.request.model_dump(include=set(Context.model_fields)),
                        payload=loaded.request.payload.model_dump(),
                    )
                    source_lineage = {
                        **loaded.lineage,
                        "input_origin": "REFERENCE_UPSTREAM_C05_C06_C02_ONLY",
                        "reference_outputs_used": False,
                    }
                knowledge = Knowledge(settings.database_url, request.knowledge_snapshot_sha256)
            if args.profile:
                data = read_json(args.profile)
                profile = ContractProfile.model_validate(data) if data else None
            if args.registry:
                request.payload.external_evidence_registry = read_models(
                    args.registry, ExternalEvidenceRegistration
                )
            if args.citations:
                request.payload.citations = read_models(args.citations, CitationValidation)
                request.payload.citation_branch_status = "COMPLETED"
            elif args.citations_completed:
                request.payload.citation_branch_status = "COMPLETED"
            use_provider = not args.input or args.replay_analyses is not None
            if use_provider:
                reviews = read_models(args.reviews, BackendReview)
                verifications = read_models(args.verifications, CriterionVerification)
                run = run_assessment(
                    ReasoningRequest(
                        **request.model_dump(include=set(Context.model_fields)),
                        payload=request.payload.model_dump(
                            include=set(ReasoningPayload.model_fields)
                        ),
                    ),
                    knowledge,
                    provider=LLMObservationProvider(
                        client=None, reviews=reviews, verifications=verifications, max_calls=0
                    ),
                    profile=profile,
                    replay_records=read_models(args.replay_analyses, CriterionAnalysis),
                )
                request.payload.observations = run.request.payload.observations
                request.payload.reasoning_provenance = {
                    "source_lineage": source_lineage,
                    "analyses": [row.model_dump(mode="json") for row in run.batch.analyses],
                    "reviews": [row.model_dump(mode="json") for row in reviews],
                    "verifications": [row.model_dump(mode="json") for row in verifications],
                    "profile": profile.model_dump(mode="json") if profile else None,
                }
            elif args.verifications or args.profile:
                raise ValueError("Profile/verifications require a provider replay")
            request = PipelineRequest.model_validate(request.model_dump())
            response = run_pipeline(request, knowledge, store=store if args.save else None)
            lineage = store.get_lineage(request.ca_id, request.run_id) if args.save else None
            metadata = {
                "mode": (
                    "REPLAY"
                    if args.replay_analyses
                    else "OFFLINE_INPUT"
                    if args.input
                    else "OFFLINE_REFERENCE_UPSTREAM"
                ),
                "db_results_saved": args.save,
                "recomputed": True,
                "source_lineage": source_lineage,
            }
        metadata = export_run(output, request, response, metadata, lineage=lineage)
        print(json.dumps({**metadata, "output_dir": str(output)}, ensure_ascii=True, indent=2))
        return 0
    except Exception as error:
        # Library errors may contain source text or connection secrets. Artifacts remain
        # absent on failure and this boundary emits only the type, never a misleading success.
        print(f"Group C failed ({type(error).__name__}); check input/context/DB.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
