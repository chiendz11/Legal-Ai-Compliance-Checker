"""CLI for a complete C07 checklist; offline by default, live API only with --live.

Run from the project root with `python -m legal_checker.modules.compliance.run_c07`.
DB access is read-only. Output files are review artifacts, not database approvals.
"""

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from legal_checker.core.config import Settings
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.input_repository import C07InputRepository, readonly_database
from legal_checker.modules.compliance.llm_contracts import CriterionAnalysis, ObservationBatch
from legal_checker.modules.compliance.reviewed_observations import BackendReview, proposal_digest
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.shared.contracts.audit import LlmAudit
from legal_checker.shared.contracts.document_intelligence import ContractProfile
from legal_checker.shared.contracts.reasoning import (
    CriterionResult,
    ExternalEvidenceRegistration,
    ReasoningRequest,
)


class JsonlAuditSink:
    """Append only X02 metadata for actual calls; never retain prompts or credentials."""

    def __init__(self, path: Path):
        self.path = path
        self.count = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # A fresh output directory is expected. Refuse to mix audit runs silently.
        self.path.open("x", encoding="utf-8").close()

    def append(self, event: LlmAudit) -> None:
        checked = LlmAudit.model_validate(event.model_dump())
        with self.path.open("a", encoding="utf-8") as output:
            output.write(checked.model_dump_json() + "\n")
        self.count += 1


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON constant is not permitted: {value}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def read_json(path: Path):
    """Read local UTF-8 review/input files without accepting ambiguous JSON."""
    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        parse_constant=_reject_constant,
        object_pairs_hook=_unique_object,
    )


def read_models(path: Path | None, model):
    """Sidecars are explicit typed lists, never backend records synthesized by AI."""
    if path is None:
        return []
    values = read_json(path)
    if not isinstance(values, list):
        raise ValueError("Review, registry and replay files must contain JSON lists")
    return [model.model_validate(value) for value in values]


def write_json(path: Path, value) -> None:
    """Keep input, proposals and results as readable UTF-8 artifacts."""
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )


@dataclass(frozen=True)
class C07Run:
    """The exact reasoner input, separate analysis records and computed findings."""

    request: ReasoningRequest
    batch: ObservationBatch
    results: list[CriterionResult]


def run_assessment(
    request: ReasoningRequest,
    knowledge: KnowledgeSnapshot,
    *,
    provider,
    profile: ContractProfile | None = None,
    replay_records=(),
) -> C07Run:
    """Evaluate the resolved checklist using an injected provider, without connections."""
    request = ReasoningRequest.model_validate(request.model_dump())
    before = request.model_dump()
    batch = ObservationBatch.model_validate(
        provider.analyze(
            request, knowledge, profile=profile, replay_records=replay_records
        ).model_dump()
    )
    if request.model_dump() != before:
        raise ValueError("ObservationProvider changed input data")
    expected = {
        criterion["tieu_chi_id"]
        for requirement in request.payload.requirements
        if requirement.version_status == "RESOLVED" and requirement.requirement_version_id is not None
        for criterion in knowledge.criteria_for(requirement.requirement_version_id)
    }
    observation_ids = [item.tieu_chi_id for item in batch.observations]
    analysis_ids = [item.tieu_chi_id for item in batch.analyses]
    if (
        len(observation_ids) != len(expected)
        or set(observation_ids) != expected
        or len(analysis_ids) != len(expected)
        or set(analysis_ids) != expected
    ):
        raise ValueError("ObservationProvider changed the criterion checklist")
    data = request.model_dump()
    data["payload"]["observations"] = [item.model_dump() for item in batch.observations]
    reasoner_input = ReasoningRequest.model_validate(data)
    results = reason(reasoner_input, knowledge)
    return C07Run(reasoner_input, batch, results)


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def save_run(
    output: Path,
    run: C07Run,
    *,
    source_input: dict,
    metadata: dict,
    verifications=(),
    profile: ContractProfile | None = None,
) -> None:
    """Save a complete review package and binding IDs without inventing review flags."""
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "source_input.json", source_input)
    write_json(output / "input.json", run.request.model_dump(mode="json"))
    write_json(output / "profile.json", profile.model_dump(mode="json") if profile else None)
    write_json(
        output / "analyses.json", [row.model_dump(mode="json") for row in run.batch.analyses]
    )
    write_json(output / "c07.json", [row.model_dump(mode="json") for row in run.results])
    write_json(
        output / "verifications.json",
        [row.model_dump(mode="json") for row in verifications],
    )
    summaries = {row.tieu_chi_id: row for row in run.batch.analyses}
    bindings = []
    owners = {row.tieu_chi_id: row.yeu_cau_ca_id for row in run.results}
    for row in run.batch.analyses:
        if row.observation_proposal is None:
            continue
        bindings.append(
            {
                key: getattr(run.request, key)
                for key in (
                    "ca_id",
                    "phien_ban_id",
                    "rule_version",
                    "legal_knowledge_version",
                    "knowledge_snapshot_sha256",
                    "run_id",
                    "trace_id",
                )
            }
            | {
                "hop_dong_id": run.request.payload.hop_dong_id,
                "yeu_cau_ca_id": owners[row.tieu_chi_id],
                "tieu_chi_id": row.tieu_chi_id,
                "proposal_sha256": proposal_digest(row.observation_proposal),
            }
        )
    write_json(output / "review_bindings.json", bindings)
    metadata = {
        **metadata,
        "case_id": run.request.ca_id,
        "contract_id": run.request.payload.hop_dong_id,
        "run_id": run.request.run_id,
        "knowledge_snapshot_sha256": run.request.knowledge_snapshot_sha256,
        "requirements": len(run.request.payload.requirements),
        "chunks": len(run.request.payload.chunks),
        "selected_c06": len(run.request.payload.retrieval),
        "observations": len(run.batch.observations),
        "verification_records": len(verifications),
        "profile_context_present": profile is not None,
        "verification_criterion_ids": [row.tieu_chi_id for row in verifications],
        "findings": dict(Counter(row.finding for row in run.results)),
        "analysis_origins": dict(Counter(row.origin for row in run.batch.analyses)),
        "analysis_errors": dict(
            Counter(row.error_code for row in run.batch.analyses if row.error_code is not None)
        ),
        "unresolved_c05_without_version": [
            row.yeu_cau_ca_id
            for row in run.request.payload.requirements
            if row.version_status != "RESOLVED" or row.requirement_version_id is None
        ],
        "db_results_saved": False,
    }
    write_json(output / "metadata.json", metadata)
    lines = [
        "# Kết quả C07",
        "",
        f"Case: `{run.request.ca_id}`; run: `{run.request.run_id}`.",
        "",
        f"Chế độ: `{metadata['mode']}`. C07 được tính mới bằng reason(); "
        "không đọc finding EXPECTED/seed.",
        "",
        f"C05: {metadata['requirements']}; C06 selected FINAL: {metadata['selected_c06']}; "
        f"Observations: {metadata['observations']}; C07: {len(run.results)}.",
        "",
        "`analyses.json` giữ proposal riêng với Observation sau kiểm tra. "
        "UNKNOWN có thể do thiếu C06, cấu hình/client, facts hoặc xác minh backend.",
        "",
        "Các trường hợp không có version chưa thể xác định criterion nằm trong metadata; "
        "không tạo criterion ID giả.",
        "",
        "| Criterion | Nguồn phân tích | Đề xuất | Finding / Review | Evidence | Lý do |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in run.results:
        analysis = summaries[result.tieu_chi_id]
        proposal = analysis.proposal.proposed_finding if analysis.proposal else "UNKNOWN"
        evidence = ", ".join(item.doan_id for item in result.evidence)
        external = ", ".join(item.bang_chung_id for item in result.external_evidence)
        lines.append(
            f"| {result.tieu_chi_id} | {analysis.origin} | {proposal} | "
            f"{result.finding} / {result.review_status} | {_cell(evidence or external or '—')} | "
            f"{_cell(result.uncertainty_reason or result.giai_thich)} |"
        )
    lines += [
        "",
        "## Review và chạy lại",
        "",
        "`review_bindings.json` chỉ chứa identity/digest để gắn review. "
        "Nó không phải BackendReview và không xác nhận bất kỳ gate nào.",
        "",
        "Review độc lập phải ghi các xác minh thật cùng verification_reference. "
        "Dùng input.json và --replay-analyses để áp dụng review cho đúng proposal đã lưu; "
        "không cần gọi lại AI hoặc tạo snapshot mới.",
        "",
        "`verifications.json` lưu xác minh backend có trước phân tích, tách khỏi "
        "BackendReview gắn với proposal sau phân tích. Khi replay cần truyền lại "
        "--verifications nếu file cũ có dữ liệu; provider kiểm tra hash ngữ cảnh.",
        "",
        "`profile.json` giữ nguyên bối cảnh C02 chưa xác minh. Khi replay một lần chạy "
        "có C02, truyền --profile cùng file đó để giữ nguyên hash ngữ cảnh.",
        "",
        "Chỉ nhật ký của những HTTP attempt thật mới được ghi vào llm_audit.jsonl. "
        "Không có audit event giả trong chế độ offline/replay.",
        "",
    ]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Live calls are an explicit action, never inferred from presence of an API key."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="CA360_001")
    parser.add_argument("--reference-run", default="CA360_001_PDF360_LS2_REFERENCE")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--criterion", action="append", default=None)
    parser.add_argument("--max-calls", type=int, default=1)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--verifications", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--replay-analyses", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser


def main(argv=None) -> int:
    """Load pinned data, run provider/reasoner, and save artifacts without DB writes."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_calls < 0:
        parser.error("--max-calls must be nonnegative")
    if args.live and args.replay_analyses:
        parser.error("--live and --replay-analyses are mutually exclusive")
    if args.replay_analyses and not args.input:
        parser.error("--replay-analyses requires --input to preserve review bindings")

    # Lazy imports keep CLI help and composition tests independent of API transport.
    from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
    from legal_checker.modules.compliance.verification import CriterionVerification

    settings = Settings.from_env()
    try:
        with readonly_database():
            if args.input:
                request = ReasoningRequest.model_validate(read_json(args.input))
                profile = None
                lineage = {"input_file": str(args.input), "context_policy": "PRESERVED_FOR_REPLAY"}
            else:
                loaded = C07InputRepository(settings.database_url).load(
                    args.case, args.reference_run
                )
                request, profile, lineage = loaded.request, loaded.profile, loaded.lineage
            # This constructor only reads an existing immutable snapshot when pinned.
            knowledge = Knowledge(
                settings.database_url, snapshot_sha256=request.knowledge_snapshot_sha256
            )
        if args.profile:
            profile_data = read_json(args.profile)
            profile = (
                ContractProfile.model_validate(profile_data) if profile_data is not None else None
            )
        if args.registry:
            data = request.model_dump()
            data["payload"]["external_evidence_registry"] = [
                item.model_dump()
                for item in read_models(args.registry, ExternalEvidenceRegistration)
            ]
            request = ReasoningRequest.model_validate(data)
        reviews = read_models(args.reviews, BackendReview)
        verifications = read_models(args.verifications, CriterionVerification)
        replay = read_models(args.replay_analyses, CriterionAnalysis)
        source_input = request.model_dump(mode="json")
        output = args.output_dir or Path("outputs/c07_runs") / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + request.run_id[-12:]
        )
        output.mkdir(parents=True, exist_ok=True)
        sink = JsonlAuditSink(output / "llm_audit.jsonl")
        client = None
        if args.live:
            from legal_checker.shared.llm.client import OpenAIResponsesClient
            from legal_checker.shared.llm.config import OpenAISettings

            client = OpenAIResponsesClient(OpenAISettings.from_env(), sink)
        try:
            provider = LLMObservationProvider(
                client=client,
                reviews=reviews,
                verifications=verifications,
                max_calls=args.max_calls,
                criterion_ids=set(args.criterion) if args.criterion else None,
            )
            run = run_assessment(
                request, knowledge, provider=provider, profile=profile, replay_records=replay
            )
        finally:
            if client is not None:
                client.close()
        mode = "LIVE_OPENAI" if args.live else "REPLAY" if args.replay_analyses else "OFFLINE"
        save_run(
            output,
            run,
            source_input=source_input,
            profile=profile,
            verifications=verifications,
            metadata={
                "mode": mode,
                "executed_at_utc": datetime.now(timezone.utc).isoformat(),
                "database_access": "READ_ONLY",
                "audit_attempts": sink.count,
                "max_criterion_calls": args.max_calls,
                "lineage": lineage,
            },
        )
        print(
            json.dumps(
                {
                    "mode": mode,
                    "case": request.ca_id,
                    "run": request.run_id,
                    "observations": len(run.batch.observations),
                    "c07": len(run.results),
                    "findings": dict(Counter(row.finding for row in run.results)),
                    "audit_attempts": sink.count,
                    "report": str(output / "report.md"),
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0
    except Exception as error:
        # Configuration errors are deliberately safe. Other library exceptions may
        # embed raw input/connection details, so only emit their type at this boundary.
        from legal_checker.shared.llm.config import LlmConfigurationError

        if isinstance(error, LlmConfigurationError):
            print(f"C07 configuration: {error}", file=sys.stderr)
        else:
            print(
                f"C07 could not complete ({type(error).__name__}). "
                "Check input/review bindings, output directory and database configuration.",
                file=sys.stderr,
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
